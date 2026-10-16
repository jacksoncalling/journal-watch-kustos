#!/usr/bin/env python3
"""05_praxis-check: the on-demand research dossier (slice 1.5).

Occasion-driven, not weekly. Reads one question file from
05_praxis-check/fragen/, runs a DEEP, non-windowed Europe PMC search, ranks
all-time (recency stays a bonus, never a filter), enriches the top N, and makes
ONE synthesis LLM call to write a German dossier answering: current evidence,
what is standard, where is the controversy.

It REUSES the verified slice-1 functions by import (fetch, enrich, rank,
synthesize, send). It does not rebuild the pipeline, does not edit the weekly
scripts, and does not touch the weekly seen.json ledger (a Praxis-Check wants to
surface older landmark papers, not dedupe them away).

Query building is Hybrid (build decision, 2026-08-23): if the question file
carries an explicit ```query block it is used verbatim (fully deterministic);
otherwise ONE bounded LLM step translates the German question into Europe PMC
queries. That planning call only ever produces search strings, never clinical
claims, so every provenance guarantee (Stufe + links set in code) is untouched.

  python scripts/praxis_check.py                    # newest question in fragen/
  python scripts/praxis_check.py --frage <path>     # a specific question file
  python scripts/praxis_check.py --dry-run          # fetch..synthesize, no send
  python scripts/praxis_check.py --plan-only        # resolve + print the query
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import check_claims
import enrich
import fetch_europepmc as fetch
import rank
import send_telegram as tg
import synthesize as synth

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "05_praxis-check"
FRAGEN = STAGE / "fragen"
OUTPUT = STAGE / "output"
VERTRAG = STAGE / "dossier-vertrag.md"
USAGE = STAGE / "usage.json"      # daily dossier-count ledger (cost guard)
PROFILE = ROOT / "profil" / "profile.md"
KANON = ROOT / "profil" / "kanon.md"

ALL_TIME_START = "1900-01-01"   # disables the weekly window: landmark trials included
PRAXIS_SORT = "CITED desc"      # most-cited first, so landmark papers surface all-time
PRAXIS_PAGE_SIZE = 200          # deep pool: landmarks sit far down the citation ranking,
                                #   so a 50-wide pool would never fetch them
PRAXIS_SEARCH_TIMEOUT = 60      # a 200-record core response is large; 30s can trip
DEFAULT_MAX_ITEMS = 20
DEFAULT_DAILY_CAP = 50          # max dossiers/day if profile.md sets no override
MAX_PLANNED_QUERIES = 3
TITLE_HIT_WEIGHT = 40           # per query concept found in a paper's TITLE
TITLE_HIT_CAP = 3               # bonus caps at 3 hits (+120), enough to lift an
                                #   on-topic RCT over an off-topic but highly-cited guideline
CARDIAC_MESH_BONUS = 40         # confirmed on-domain via MeSH (like one title hit);
                                #   a bonus, not a filter, so MeSH-less papers are not sunk
STOP_TOKENS = {"and", "or", "not", "src", "med", "first", "pdate"}

# Prescriptive dosing/selection verbs. A hit in the MODEL BODY (scanned before
# finalize adds the footer) is a possible dose-as-advice breach. Kept tight to
# dose/administration/model-selection so common German imperatives do not trip
# it, and so the mandatory footer ("Dosierungsangaben", "prüfen") never matches.
DOSE_DIRECTIVE = re.compile(
    r"\b(dosieren|verabreichen|titrieren|applizieren)\s+sie\b"
    r"|\bw[äa]hlen\s+sie\b[^.]{0,40}\bmodell\b"
    r"|\bempfohlene\s+dosis\b",
    re.I)


class PraxisError(Exception):
    """A run that could not produce a dossier (no candidates, no queries, no
    provider). A normal `Exception` (not SystemExit) so a web caller's
    `except Exception` handles it and turns it into a clean error response."""


class DailyLimitError(PraxisError):
    """The daily dossier cap is reached. A PraxisError subclass so the CLI's
    `except PraxisError` still catches it, but the web layer can catch it first
    and return a rate-limit response (429) distinct from 'no candidates' (422)."""


# --------------------------------------------------------------------------- #
# question file
# --------------------------------------------------------------------------- #
def pick_question(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.is_absolute():
            p = (ROOT / arg).resolve()
        return p
    files = sorted(FRAGEN.glob("*.md"))
    if not files:
        raise SystemExit(f"no question files in {FRAGEN}")
    return files[-1]


def _section(text: str, name: str) -> str:
    """Return the body of a `## <name>` section, up to the next `## ` heading."""
    m = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)",
                  text, re.M | re.S)
    return m.group(1).strip() if m else ""


def parse_question(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    tm = re.search(r"^#\s+Frage:\s*(.+?)\s*$", text, re.M)
    title = tm.group(1).strip() if tm else path.stem

    frage = _section(text, "Frage")
    kontext = _section(text, "Kontext")

    mi = re.search(r"max_items\s*:\s*(\d+)", kontext or text)
    max_items = int(mi.group(1)) if mi else DEFAULT_MAX_ITEMS

    # Optional explicit query in a ```query fenced block. Strip HTML comments
    # first so a commented-out example block is not mistaken for a real query.
    no_comments = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    qm = re.search(r"```query\s*(.*?)```", no_comments, re.S)
    explicit_query = qm.group(1).strip() if qm else ""

    return {
        "path": path,
        "slug": path.stem,
        "title": title,
        "frage": frage,
        "kontext": kontext,
        "max_items": max_items,
        "explicit_query": explicit_query,
    }


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:60].rstrip("-")) or "frage"


def question_from_text(text: str, max_items: int = DEFAULT_MAX_ITEMS,
                       explicit_query: str = "") -> dict:
    """Build the same question dict from a raw string (a web form or a Telegram
    message) instead of a fragen/*.md file. This is the seam the web app calls:
    it hands the pipeline an in-memory question and gets a dossier back, so the
    interface never touches the search/synthesis/guardrail code."""
    text = (text or "").strip()
    first = text.splitlines()[0].strip() if text else "Praxis-Check"
    title = first if len(first) <= 90 else first[:88].rsplit(" ", 1)[0] + "…"
    return {
        "path": None,
        "slug": _slugify(title),
        "title": title,
        "frage": text,
        "kontext": "",
        "max_items": max_items,
        "explicit_query": explicit_query,
    }


# --------------------------------------------------------------------------- #
# provider calls (reuse synthesize's provider seam for BOTH planning + dossier)
# --------------------------------------------------------------------------- #
def call_llm(system: str, user: str, cfg: dict, purpose: str,
             temperature: float | None = None) -> str:
    """Run the configured provider order (primary, then fallback). Returns the
    text, or '' if every provider missed / errored / refused. `temperature=0`
    pins the query planner to reproducible decoding; the dossier call leaves it
    None (provider default)."""
    order = [cfg["primary"]] + ([cfg["fallback"]] if cfg["fallback"] else [])
    for name in order:
        r = synth.run_provider(name, system, user, cfg, temperature)
        if r is None:
            continue
        if r.refused:
            print(f"  [{name}] refused during {purpose}. Trying next.",
                  file=sys.stderr)
            continue
        if r.text.strip():
            print(f"  [{purpose}] {r.provider}/{r.model}  "
                  f"in={r.input_tokens} out={r.output_tokens}")
            return r.text
    return ""


PLAN_SYSTEM = (
    "Du bist ein Suchstrategie-Helfer fuer Europe PMC (PubMed/MEDLINE). "
    "Uebersetze die medizinische Frage in ein bis drei Europe-PMC-Boolean-Queries. "
    "Regeln: englische Fachbegriffe und MeSH-nahe Synonyme in OR-Gruppen, "
    "Anfuehrungszeichen fuer Phrasen, Facetten mit AND verbunden, an jede Query "
    "' AND SRC:MED' anhaengen. Gib NUR die Queries aus, eine pro Zeile, keine "
    "Nummerierung, keine Erklaerung, keine Codebloecke."
)


def plan_queries(q: dict, cfg: dict) -> list[str]:
    user = (f"Frage: {q['frage']}\n\n"
            + (f"Kontext: {q['kontext']}\n\n" if q['kontext'] else "")
            + "Gib die Europe-PMC-Queries aus.")
    text = call_llm(PLAN_SYSTEM, user, cfg, "query-planung", temperature=0)
    queries: list[str] = []
    for line in text.splitlines():
        s = line.strip().strip("`").strip()
        # Strip a leading list marker the model may add despite the prompt
        # (e.g. "1.", "1)", "- ", "* "); left in, it corrupts the EPMC query.
        s = re.sub(r"^\s*(?:\d+[.)]|[-*])\s+", "", s)
        if not s or s.startswith("#") or s.lower().startswith("query"):
            continue
        if "SRC:MED" not in s.upper():
            s = f"{s} AND SRC:MED"
        queries.append(s)
        if len(queries) >= MAX_PLANNED_QUERIES:
            break
    return queries


def resolve_queries(q: dict, cfg: dict) -> list[str]:
    if q["explicit_query"]:
        print("query: explicit (from question file, deterministic)")
        return [q["explicit_query"]]
    print("query: none in file, planning via LLM (Hybrid fallback)")
    planned = plan_queries(q, cfg)
    if not planned:
        raise PraxisError("query planning produced no usable search query; "
                          "try rephrasing the question or add an explicit query")
    return planned


# --------------------------------------------------------------------------- #
# search + rank + enrich (reused slice-1 functions, composed here)
# --------------------------------------------------------------------------- #
def mesh_of(rec: dict) -> list[str]:
    """MeSH descriptor names (lowercased) from a raw Europe PMC record. Captured
    here in the Praxis-Check, not in the shared weekly normalise(), so the weekly
    scripts stay untouched. Empty list when the record carries no MeSH (~25% of
    the all-time pool: non-MEDLINE sources), in which case the MeSH gate abstains
    and the string subject gate decides."""
    ml = (rec.get("meshHeadingList") or {}).get("meshHeading") or []
    return [m["descriptorName"].lower() for m in ml if m.get("descriptorName")]


def run_search(queries: list[str], ua: str) -> list[dict]:
    end = date.today().isoformat()
    by_key: dict[str, dict] = {}
    for i, query in enumerate(queries):
        results = fetch.search_topic(query, ALL_TIME_START, end, ua,
                                     sort=PRAXIS_SORT, page_size=PRAXIS_PAGE_SIZE,
                                     timeout=PRAXIS_SEARCH_TIMEOUT)
        print(f"  q{i+1}: {len(results)} hits  |  {query[:70]}")
        for rec in results:
            key = fetch.dedupe_key(rec)
            if not key:
                continue
            label = f"q{i+1}"
            if key in by_key:
                if label not in by_key[key]["matchedTopics"]:
                    by_key[key]["matchedTopics"].append(label)
            else:
                norm = fetch.normalise(rec, [label])
                norm["mesh"] = mesh_of(rec)
                by_key[key] = norm
        time.sleep(0.25)
    return list(by_key.values())


def parse_domain(text: str) -> dict:
    """Read the Domain-Gate block from profile.md: cardiac-context MeSH anchors
    (ranking bonus) and negative MeSH anchors (hard drop). Both are lists of
    lowercased substrings matched against a paper's MeSH descriptors. Domain-wide
    and fixed, so they hold for every cardiac-anaesthesia question, not one."""
    cardiac: list[str] = []
    negative: list[str] = []
    section: list[str] | None = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("### ") and "cardiac" in s.lower():
            section = cardiac
            continue
        if s.startswith("### ") and ("negative" in s.lower() or "drop" in s.lower()):
            section = negative
            continue
        if s.startswith("## "):          # left the Domain-Gate block (h2, not h3)
            section = None
            continue
        if section is not None:
            m = re.match(r"^-\s+(.+?)\s*$", s)
            if m:
                section.append(m.group(1).lower())
    return {"cardiac": cardiac, "negative": negative}


def _mesh_hit(mesh: list[str], anchors: list[str]) -> bool:
    return any(any(a in d for a in anchors) for d in mesh)


def off_domain(cand: dict, domain: dict) -> bool:
    """True if a paper's MeSH marks it animal/oncology AND carries no cardiac
    context (so it is out of her field). No MeSH -> not gated here."""
    mesh = cand.get("mesh") or []
    if not mesh or not domain["negative"]:
        return False
    return (_mesh_hit(mesh, domain["negative"])
            and not _mesh_hit(mesh, domain["cardiac"]))


def _concepts_from(fragment: str) -> set[str]:
    """Salient terms from a query fragment: quoted phrases plus bare tokens,
    minus boolean/field operators and wildcards."""
    terms: set[str] = set()
    for phrase in re.findall(r'"([^"]+)"', fragment):
        terms.add(phrase.lower().strip())
    bare = re.sub(r'"[^"]+"', " ", fragment)       # drop quoted spans first
    for tok in re.findall(r"[A-Za-z][A-Za-z-]{3,}", bare):
        t = tok.lower().rstrip("*")
        if t not in STOP_TOKENS:
            terms.add(t)
    return terms


def query_concepts(queries: list[str]) -> set[str]:
    """All salient topic terms across the resolved queries. Used to score how
    on-topic a paper's TITLE is (a citation-sorted all-time pool otherwise floats
    famous but off-topic papers that match the broad OR terms only in passing)."""
    terms: set[str] = set()
    for q in queries:
        terms |= _concepts_from(q)
    return terms


def subject_concepts(queries: list[str]) -> set[str]:
    """Concepts from the FIRST AND-facet of each query, i.e. the intervention or
    drug the question is actually about. The planner reliably places the subject
    first (corticosteroid, tranexamic, dexmedetomidine, ...), so requiring at
    least one of these in a paper's title/abstract stops highly-cited but
    off-subject perioperative reviews (lidocaine, liraglutide, selenium) from
    ranking top just because they match the broad context facet (cardiac surgery,
    perioperative). This is the sharpened relevance floor: gate on the subject
    actor, not on any shared word."""
    subj: set[str] = set()
    for q in queries:
        first = re.split(r"(?i)\bAND\b", q, maxsplit=1)[0]
        subj |= _concepts_from(first)
    return subj


def is_retracted(pub_types: list[str]) -> bool:
    """True if Europe PMC marks the record as a retracted article or a retraction
    notice. Such records are dropped before ranking so a dossier never rests on
    retracted evidence. (Europe PMC pubType coverage lags the literature; this is
    the cheap 80/20, not a full Retraction Watch cross-check.)"""
    joined = " ".join(pub_types or []).lower()
    return "retracted publication" in joined or "retraction of publication" in joined


def title_bonus(cand: dict, concepts: set[str]) -> int:
    title = (cand.get("title") or "").lower()
    hits = sum(1 for t in concepts if t in title)
    return min(hits, TITLE_HIT_CAP) * TITLE_HIT_WEIGHT


def rank_all(cands: list[dict], profile_text: str,
             queries: list[str], domain: dict | None = None) -> list[dict]:
    prof = rank.parse_profile(profile_text)
    kanon_kw = rank.kanon_keywords(KANON)
    concepts = query_concepts(queries)
    subj = subject_concepts(queries)
    if domain is None:
        domain = parse_domain(profile_text)
    today = date.today()
    ranked = []
    for c in cands:
        stufe = rank.evidence_level(c.get("pubTypes", []))
        total, breakdown = rank.score(c, stufe, prof["trust"], kanon_kw, today)
        tb = title_bonus(c, concepts)              # Praxis-only topical relevance
        total += tb
        breakdown["title_relevance"] = tb
        cb = CARDIAC_MESH_BONUS if _mesh_hit(c.get("mesh") or [],
                                             domain["cardiac"]) else 0
        total += cb
        breakdown["cardiac_mesh"] = cb
        item = dict(c)
        item["stufe"] = stufe
        item["score"] = round(total, 1)
        item["score_breakdown"] = breakdown
        # Subject-actor gate: does the paper mention the intervention at all, or
        # only the broad context? Absent a subject set, treat all as on-subject.
        # Match a trailing-plural query term against a singular in the paper too
        # ("corticosteroids" in the query vs "corticosteroid" in the abstract).
        hay = f"{c.get('title','')} {c.get('abstract','')}".lower()
        item["on_subject"] = (not subj) or any(
            t in hay or (t.endswith("s") and t[:-1] in hay) for t in subj)
        ranked.append(item)
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


ENRICH_MAX_WORKERS = 8   # parallel network round trips (B2). Two independent
                          # services (Unpaywall, EBI full text), so a modest
                          # worker cap speeds the batch without hammering either.


def _oa_lookup(c: dict, email: str, ua: str) -> str | None:
    try:
        return enrich.unpaywall_oa_url(c["doi"], email, ua)
    except Exception as e:
        print(f"  unpaywall error {c['doi']}: {e}", file=sys.stderr)
        return None


def _fulltext_lookup(c: dict, ua: str) -> str | None:
    try:
        return enrich.fulltext_excerpt(c["pmcid"], ua)
    except Exception as e:
        print(f"  fulltext error {c['pmcid']}: {e}", file=sys.stderr)
        return None


def enrich_top(selected: list[dict], ua: str, email: str) -> None:
    """OA link + full-text excerpt for the selected papers only (in place). The
    corpus is large, so enrich AFTER ranking, not before.

    The per-paper round trips are independent network calls (Unpaywall for the
    OA link, EBI for the full-text excerpt), so they run in a ThreadPoolExecutor
    instead of one at a time. Python analogue of Promise.allSettled, never
    Promise.all: `_oa_lookup`/`_fulltext_lookup` already catch their own
    exceptions and return None on a miss, so one paper's 404/timeout/not-OA
    never sinks the batch, same as the previous serial loop. `selected` keeps
    its order (mutated in place by object, not by completion order); the
    summary counts and their wording are unchanged."""
    oa_jobs = [c for c in selected if c.get("doi") and not c.get("oaUrl")]
    ft_jobs = [c for c in selected if c.get("pmcid") and not c.get("fullTextExcerpt")]

    oa = ft = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=ENRICH_MAX_WORKERS) as ex:
        oa_futures = {ex.submit(_oa_lookup, c, email, ua): c for c in oa_jobs}
        ft_futures = {ex.submit(_fulltext_lookup, c, ua): c for c in ft_jobs}
        for fut in concurrent.futures.as_completed(oa_futures):
            u = fut.result()
            if u:
                oa_futures[fut]["oaUrl"] = u
                oa += 1
        for fut in concurrent.futures.as_completed(ft_futures):
            x = fut.result()
            if x:
                ft_futures[fut]["fullTextExcerpt"] = x
                ft += 1
    print(f"  enriched top {len(selected)}: +{oa} OA links, +{ft} full-text")


# --------------------------------------------------------------------------- #
# synthesis + deterministic assembly
# --------------------------------------------------------------------------- #
def build_user(q: dict, selected: list[dict]) -> str:
    papers = [synth.paper_payload(c) for c in selected]
    return (
        f"FRAGE (rahmt das Dossier):\n{q['frage']}\n\n"
        + (f"KONTEXT:\n{q['kontext']}\n\n" if q["kontext"] else "")
        + "Hier sind die gerankten Paper als JSON (evidence_basis = Volltext-"
        "Auszug oder Abstract). Schreibe das Dossier exakt nach dem Vertrag im "
        "System-Prompt. Belege tragende Aussagen inline nur mit `(PMID <pmid>)` "
        "aus den mitgelieferten PMIDs. Schreibe KEINE Stufe-, Provenienz- oder "
        "Link-Zeilen und KEINE Quellen-Liste; der Code haengt sie an. Nutze nur "
        "evidence_basis; was dort nicht steht, lass weg.\n\n"
        + json.dumps(papers, ensure_ascii=False, indent=2)
    )


def validate_citations(dossier: str, selected: list[dict]) -> None:
    known = {str(c["pmid"]) for c in selected if c.get("pmid")}
    cited: set[str] = set()
    for grp in re.findall(r"\(PMID\s+([\d,\s]+)\)", dossier):
        for pmid in re.findall(r"\d+", grp):
            cited.add(pmid)
    if not cited:
        print("  WARN: dossier has NO inline (PMID ...) citations; the contract "
              "requires inline provenance on load-bearing claims", file=sys.stderr)
    unknown = cited - known
    if unknown:
        print(f"  WARN: dossier cites {len(unknown)} PMID(s) not in the selected "
              f"set (possible hallucination): {sorted(unknown)}", file=sys.stderr)


def scan_dose_directives(body: str) -> None:
    """Warn if the model wrote a prescriptive dosing/selection directive (a
    dose-as-advice guardrail breach). Scans the model body BEFORE finalize adds
    the footer, so the mandatory footer's own wording never trips it. Warn only,
    never rewrite: a false positive must not silently mangle the prose."""
    if DOSE_DIRECTIVE.search(body):
        n = len(DOSE_DIRECTIVE.findall(body))
        print(f"  WARN: {n} prescriptive dosing/selection phrase(s) in the dossier "
              f"body (possible dose-as-advice breach); review before sending",
              file=sys.stderr)


SNIPPET_CHARS = 240  # tap-to-preview card length, plain truncation of the abstract


def citation_view(selected: list[dict]) -> list[dict]:
    """One JSON-serializable object per selected paper, for the web API's
    `citations` field (Work package A, A2). Drawn ONLY from fields the pipeline
    already set (rank.evidence_level via `stufe`, A1's study_type_label,
    enrich_top's `oaUrl`/`fullTextExcerpt`); fetches nothing new. Same
    provenance guarantee as `assemble_quellen`: stufe, study_type and full_text
    are set here in code, never by the model."""
    out = []
    for c in selected:
        pmid = c.get("pmid")
        year = None
        d = c.get("date") or ""
        m = re.match(r"^(\d{4})", d)
        if m:
            year = int(m.group(1))
        abstract = (c.get("abstract") or "").strip()
        snippet = abstract[:SNIPPET_CHARS].rstrip()
        if len(abstract) > SNIPPET_CHARS:
            snippet += "…"
        out.append({
            "pmid": pmid,
            "title": c.get("title"),
            "journal": c.get("journal"),
            "year": year,
            "study_type": rank.study_type_label(c.get("pubTypes", [])),
            "stufe": c.get("stufe"),
            "doi": c.get("doi"),
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}" if pmid else None,
            "oa_url": c.get("oaUrl"),
            "full_text": bool(c.get("fullTextExcerpt")),
            "snippet": snippet,
        })
    return out


def assemble_quellen(selected: list[dict]) -> str:
    lines = ["## Quellen", ""]
    for i, c in enumerate(selected, 1):
        title = c.get("title") or "(ohne Titel)"
        journal = c.get("journal") or "?"
        d = c.get("date") or "?"
        pmid = c.get("pmid") or "?"
        lines.append(f"{i}. {title}")
        lines.append(f"   {journal}, {d} · PMID {pmid}")
        lines.append(f"   {synth.fact_line(c)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def strip_model_labels(text: str) -> str:
    """Remove any Stufe/provenance/anchor tokens the model wrote despite the
    contract; the code owns those (same discipline as synthesize.inject_facts)."""
    text = re.sub(r"\[Stufe\s*\d\]", "", text)
    text = re.sub(r"\[(?:NUR ABSTRACT|VOLLTEXT)\]", "", text)
    text = re.sub(r"\[\[PMID:\s*\d+\s*\]\]", "", text)
    return text


def finalize(body: str, queries: list[str], selected: list[dict],
             q: dict) -> str:
    body = strip_model_labels(body)
    body = synth.strip_dashes(body)
    # Drop any footer the model wrote (the code re-adds the canonical one as the
    # very last line). Match on the stable opening clause, not the exact string,
    # so a footer with drifted spacing/punctuation does not survive as a second
    # copy. FOOTER already had strip_dashes applied above so both sides match.
    body = re.sub(r"Kein Ersatz f[üu]r klinische Entscheidungen[^\n]*", "",
                  body).rstrip()

    heading = f"# Praxis-Check: {q['title']}\n"
    such = ("## Verwendete Suchanfrage\n\n"
            + "\n".join(f"- `{query}`" for query in queries) + "\n")
    quellen = assemble_quellen(selected)

    parts = [heading, body, such, quellen, synth.FOOTER + "\n"]
    out = "\n\n".join(p.strip("\n") for p in parts) + "\n"
    return re.sub(r"\n{3,}", "\n\n", out)


def synthesize_dossier(q: dict, selected: list[dict], cfg: dict,
                       profile_text: str) -> str | None:
    vertrag = VERTRAG.read_text(encoding="utf-8")
    system = (vertrag + "\n\n---\n\n# Profil der Leserin (Kontext)\n\n"
              + profile_text
              + "\n\n---\n\n# Die zu beantwortende Frage\n\n" + q["frage"])
    user = build_user(q, selected)
    text = call_llm(system, user, cfg, "dossier")
    return text or None


# --------------------------------------------------------------------------- #
# send (reuse send_telegram's splitter + API call)
# --------------------------------------------------------------------------- #
def send_dossier(path: Path) -> int:
    token = tg.load_env("TELEGRAM_BOT_TOKEN")
    chat_id = tg.load_env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("No TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID; skipping send.",
              file=sys.stderr)
        return 2
    chunks = tg.split_messages(path.read_text(encoding="utf-8"))
    print(f"sending {path.name} in {len(chunks)} message(s) to {chat_id}")
    for i, chunk in enumerate(chunks, 1):
        resp = tg.tg_call(token, "sendMessage", {
            "chat_id": chat_id, "text": chunk,
            "disable_web_page_preview": "true"})
        if not resp.get("ok"):
            print(f"  message {i}/{len(chunks)} failed: {resp}", file=sys.stderr)
            return 1
        print(f"  sent {i}/{len(chunks)} ({len(chunk)} chars)")
        time.sleep(0.4)
    print("delivered.")
    return 0


# --------------------------------------------------------------------------- #
# daily usage cap: a file-based ledger (like seen.json) so a runaway loop or a
# few eager testers cannot run the API bill up without bound. Global per day,
# enforced in build_dossier so the CLI and the web app share one guard. The
# provider-side budget alert (AI Studio) is the hard backstop under this.
# --------------------------------------------------------------------------- #
def daily_cap(profile_text: str) -> int:
    m = re.search(r"max_dossiers_per_day\s*:\s*(\d+)", profile_text)
    return int(m.group(1)) if m else DEFAULT_DAILY_CAP


def _read_usage() -> dict:
    today = date.today().isoformat()
    if USAGE.exists():
        try:
            d = json.loads(USAGE.read_text(encoding="utf-8"))
            if d.get("date") == today:
                return {"date": today, "count": int(d.get("count", 0))}
        except Exception:
            pass                      # unreadable/other-day ledger -> fresh day
    return {"date": today, "count": 0}


def check_daily_cap(cap: int) -> None:
    """Raise DailyLimitError if today's dossier count already reached the cap."""
    u = _read_usage()
    if u["count"] >= cap:
        raise DailyLimitError(f"daily limit reached ({u['count']}/{cap} dossiers "
                              "today); please try again tomorrow")


def record_dossier() -> None:
    """Count one completed dossier against today's cap. Called only on success,
    so a run that finds no candidates does not consume a slot."""
    u = _read_usage()
    u["count"] += 1
    USAGE.write_text(json.dumps(u), encoding="utf-8")


# --------------------------------------------------------------------------- #
# callable core: question dict in -> dossier out. Shared by the CLI and the web
# app, so the guardrails (finalize, code-built Quellen, citation validation)
# live in exactly one place and every interface goes through them.
# --------------------------------------------------------------------------- #
EVIDENCE_SCHEMA_VERSION = 1


def evidence_record(q: dict, queries: list[str], selected: list[dict],
                    body: str) -> dict:
    """What the synthesis call actually saw, saved next to the dossier so it can
    be audited or replayed later (scripts/check_claims.py). `papers` holds the
    exact `paper_payload` objects sent to the model, so `evidence_basis` is the
    text the claims must trace back to; `provenance` is the code-set label.
    `synthesis_raw` is the model prose before finalize, so model output and
    code-added parts stay separable."""
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "reconstructed": False,
        "question": {"title": q.get("title"), "frage": q.get("frage"),
                     "kontext": q.get("kontext")},
        "queries": queries,
        "synthesis_raw": body,
        "papers": [{**synth.paper_payload(c),
                    "provenance": synth.provenance(c),
                    "on_subject": c.get("on_subject"),
                    "score": c.get("score")} for c in selected],
    }


@dataclass
class DossierResult:
    dossier: str
    queries: list[str]
    selected: list[dict]
    evidence: dict | None = None


def dossier_stages(q: dict, *, profile_text: str | None = None,
                   enforce_limit: bool = True):
    """Generator over the guarded pipeline: resolve queries, fetch, filter,
    rank, enrich, synthesize, finalize. `build_dossier` below just drains this
    generator; the web app's streaming endpoint (Work package B1) iterates it
    directly to emit progress as each stage lands. One implementation, two
    consumers, so nothing forks the guardrails (finalize, citation validation,
    dose-directive scan, the daily cap) that live here.

    Yields `(stage, payload)` tuples, in order:
      ("queries",  {"queries": [...]})                      resolved search queries
      ("selected", {"selected": [...], "count": N})          post rank + enrich
      ("synthesis", {"text": "..."})                         raw model prose, pre-finalize
      ("done", {"dossier": "...", "queries": [...], "selected": [...],
                "evidence": {...}})                       evidence_record, for audit

    Raises `PraxisError` (or `DailyLimitError`) on a hard failure, same as
    `build_dossier` always has; a caller draining the generator sees the
    exception at the point in the pipeline where it happened.

    `enforce_limit` gates the run on a global daily cap (`max_dossiers_per_day`
    in profile.md, default 50) so a loop or eager testers cannot run the bill up.
    The benchmark harness passes False so evaluation runs are never blocked and
    never consume the users' daily quota."""
    if profile_text is None:
        profile_text = PROFILE.read_text(encoding="utf-8")
    cfg = synth.parse_synthese_config(profile_text)
    if enforce_limit:
        check_daily_cap(daily_cap(profile_text))
    contact = fetch.parse_profile(profile_text)["contact_email"] or "unknown@example.com"
    ua = f"journal-watch/0.1 (+{contact})"

    domain = parse_domain(profile_text)
    queries = resolve_queries(q, cfg)
    for query in queries:
        print(f"  -> {query}")
    yield ("queries", {"queries": queries})

    print("\n=== fetch (all-time) ===")
    cands = run_search(queries, ua)
    n_raw = len(cands)
    cands = [c for c in cands if not is_retracted(c.get("pubTypes", []))]
    n_ret = n_raw - len(cands)
    if n_ret:
        print(f"  dropped {n_ret} retracted/retraction-notice record(s)")
    n_before = len(cands)
    cands = [c for c in cands if not off_domain(c, domain)]
    n_dom = n_before - len(cands)
    if n_dom:
        print(f"  dropped {n_dom} off-domain record(s) (animal/oncology MeSH, no cardiac)")
    print(f"  {len(cands)} unique candidates")
    if not cands:
        raise PraxisError("no candidates found for this question")

    print("\n=== rank (all-time, recency as bonus, subject-gated, MeSH-aware) ===")
    ranked = rank_all(cands, profile_text, queries, domain)
    # Subject-actor gate: prefer papers that mention the intervention, not just
    # the broad context. Both partitions stay score-sorted, so on-subject papers
    # always outrank off-subject ones regardless of citations, and off-subject
    # only backfills when a small literature cannot fill max_items on its own.
    on = [r for r in ranked if r["on_subject"]]
    off = [r for r in ranked if not r["on_subject"]]
    selected = (on + off)[: q["max_items"]]
    backfill = max(0, len(selected) - len(on))
    print(f"  ranked {len(ranked)} ({len(on)} on-subject), selected top "
          f"{len(selected)}"
          + (f", {backfill} off-subject backfill" if backfill else ""))
    for s in selected[:10]:
        flag = " " if s["on_subject"] else "~"     # ~ marks an off-subject backfill
        print(f"   {flag}Stufe {s['stufe']}  score {s['score']:>6}  "
              f"{(s.get('journalAbbrev') or '?')[:24]:<24}  {(s.get('title') or '')[:44]}")

    print("\n=== enrich (top N) ===")
    enrich_top(selected, ua, contact)
    yield ("selected", {"selected": selected, "count": len(selected)})

    print("\n=== synthesize (one LLM call) ===")
    body = synthesize_dossier(q, selected, cfg, profile_text)
    if body is None:
        raise PraxisError("no provider produced a dossier (missing keys, errors, "
                          "or refusals)")
    validate_citations(body, selected)
    scan_dose_directives(body)
    yield ("synthesis", {"text": body})

    dossier = finalize(body, queries, selected, q)
    if enforce_limit:
        record_dossier()      # count only on success, after synthesis spend
    yield ("done", {"dossier": dossier, "queries": queries, "selected": selected,
                    "evidence": evidence_record(q, queries, selected, body)})


def build_dossier(q: dict, *, profile_text: str | None = None,
                  enforce_limit: bool = True) -> DossierResult:
    """The whole pipeline for one question, returning the finished dossier
    markdown. Writes nothing and sends nothing; callers decide what to do with
    the result. Raises PraxisError on a hard failure so a web caller can turn it
    into a clean error response instead of a traceback.

    Drains `dossier_stages` (see above) to a single result; this is the
    non-streaming shape the CLI, the benchmark harness, and `POST /praxis` all
    still use unchanged."""
    dossier = queries = selected = evidence = None
    for stage, payload in dossier_stages(q, profile_text=profile_text,
                                         enforce_limit=enforce_limit):
        if stage == "queries":
            queries = payload["queries"]
        elif stage == "done":
            dossier = payload["dossier"]
            selected = payload["selected"]
            evidence = payload["evidence"]
    return DossierResult(dossier=dossier, queries=queries, selected=selected,
                         evidence=evidence)


def evidence_path(dossier_path: Path) -> Path:
    """`<datum>-<slug>.md` -> `<datum>-<slug>.evidence.json`, same folder."""
    return dossier_path.with_suffix(".evidence.json")


def dossier_filename(q: dict) -> str:
    # Strip a leading YYYY-MM-DD from the slug so a dated question filename does
    # not double the date in the dossier name.
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", q["slug"])
    return f"{date.today().isoformat()}-{slug}.md"


# --------------------------------------------------------------------------- #
# main (CLI): question FILE in -> write dossier -> send via Telegram
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Journal Watch Praxis-Check (dossier).")
    ap.add_argument("--frage", help="path to a specific question file")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch..synthesize + write dossier, but do not send")
    ap.add_argument("--plan-only", action="store_true",
                    help="resolve and print the search query, then stop")
    args = ap.parse_args(argv)

    profile_text = PROFILE.read_text(encoding="utf-8")
    q = parse_question(pick_question(args.frage))
    print(f"question: {q['path'].name}  |  max_items={q['max_items']}")
    print(f"title: {q['title']}")

    try:
        if args.plan_only:
            cfg = synth.parse_synthese_config(profile_text)
            for query in resolve_queries(q, cfg):
                print(f"  -> {query}")
            return 0
        result = build_dossier(q, profile_text=profile_text)
    except PraxisError as e:
        print(f"{e}.", file=sys.stderr)
        return 1

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / dossier_filename(q)
    out.write_text(result.dossier, encoding="utf-8")
    print(f"\nwrote dossier -> {out}")
    ev = evidence_path(out)
    ev.write_text(json.dumps(result.evidence, ensure_ascii=False, indent=2),
                  encoding="utf-8")
    print(f"wrote evidence -> {ev}")
    # Warn-only claim check (numbers vs the evidence the model saw); full report:
    # python scripts/check_claims.py <dossier>
    findings = check_claims.check(result.dossier, result.evidence)
    n_fail = sum(f.level == "FAIL" for f in findings)
    n_warn = sum(f.level == "WARN" for f in findings)
    if n_fail or n_warn:
        print(f"  WARN: claim check {n_fail} FAIL, {n_warn} WARN; run "
              f"scripts/check_claims.py {out.name}", file=sys.stderr)

    if args.dry_run:
        print("\n=== send (skipped: --dry-run) ===")
        print("dry run complete: dossier written, nothing sent.")
        return 0

    print("\n=== send ===")
    rc = send_dossier(out)
    if rc == 1:
        return 1        # a real send failure is loud; a missing token (2) is not
    print("\npraxis-check complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
