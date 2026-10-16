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
    kind = "planner" if purpose == "query-planung" else "dossier"
    for name in order:
        budget = (cfg.get("thinking") or {}).get(kind) if name == "gemini" else None
        t = time.perf_counter()
        r = synth.run_provider(name, system, user, cfg, temperature, budget)
        if r is None:
            continue
        if r.refused:
            print(f"  [{name}] refused during {purpose}. Trying next.",
                  file=sys.stderr)
            continue
        if r.text.strip():
            print(f"  [{purpose}] {r.provider}/{r.model}  "
                  f"in={r.input_tokens} out={r.output_tokens} "
                  f"thoughts={r.thought_tokens} "
                  f"thinking={'default' if budget is None else budget} "
                  f"{time.perf_counter() - t:.1f}s")
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


def parse_ambiguous(profile_text: str) -> dict[str, list[str]]:
    """`## Mehrdeutige Abkürzungen` in profile.md: abbreviation -> spelled-out
    phrases, for abbreviations that are also ordinary English words (HIT)."""
    m = re.search(r"^## Mehrdeutige Abk\S*.*?$(.*?)(?=^## |\Z)", profile_text, re.M | re.S)
    out: dict[str, list[str]] = {}
    for line in (m.group(1) if m else "").splitlines():
        lm = re.match(r"^-\s+([A-Za-z0-9]+)\s*:\s*(.+?)\s*$", line.strip())
        if lm:
            out[lm.group(1).upper()] = [p.strip() for p in lm.group(2).split("|") if p.strip()]
    return out


def rewrite_ambiguous(query: str, amb: dict[str, list[str]]) -> tuple[str, list[str]]:
    """Replace every UNQUOTED ambiguous abbreviation with its quoted expansion.
    Europe PMC ignores case, so bare `HIT` matches the word "hit" and floods a
    citation-sorted pool (benchmark 2026-10-16: 0 of 20 papers on-subject).
    Quoted phrases ("HIT antibodies") and field names are left alone."""
    changed: list[str] = []

    def expand(abbr: str) -> str:
        phrases = [f'"{p}"' for p in amb[abbr.upper()]]
        changed.append(abbr)
        return phrases[0] if len(phrases) == 1 else "(" + " OR ".join(phrases) + ")"

    parts = re.split(r'("[^"]*")', query)            # odd indices are quoted spans
    for i in range(0, len(parts), 2):
        for abbr in amb:
            parts[i] = re.sub(rf"(?<![\w\"-]){re.escape(abbr)}(?![\w\":-])",
                              lambda mm: expand(mm.group(0)), parts[i], flags=re.I)
    return "".join(parts), changed


# Words about the state of a debate, not about the topic. A facet made only of
# these ("controversy OR debate OR uncertainty") filters for papers that USE
# those words, not for papers on the question: dropped from planned queries.
META_TERMS = {"controversy", "controversies", "controversial", "debate", "debated",
              "disagreement", "uncertainty", "uncertain", "conflicting evidence",
              "conflicting", "unresolved", "open questions", "open question"}
META_COMPANIONS = {"guidelines", "guideline", "recommendations", "consensus"}


def _split_top(text: str, op: str) -> list[str]:
    """Split on a boolean operator at bracket depth 0, outside quotes."""
    parts, depth, quote, buf, i = [], 0, False, "", 0
    pat = re.compile(rf"\s+{op}\s+", re.I)
    while i < len(text):
        ch = text[i]
        if ch == '"':
            quote = not quote
        elif not quote and ch == "(":
            depth += 1
        elif not quote and ch == ")":
            depth -= 1
        if not quote and depth == 0:
            m = pat.match(text, i)
            if m:
                parts.append(buf)
                buf, i = "", m.end()
                continue
        buf += ch
        i += 1
    parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def _strip_parens(text: str) -> tuple[str, bool]:
    """'(a OR b)' -> ('a OR b', True) when the outer brackets enclose it all."""
    t = text.strip()
    if not (t.startswith("(") and t.endswith(")")):
        return t, False
    depth, quote = 0, False
    for i, ch in enumerate(t):
        if ch == '"':
            quote = not quote
        elif not quote and ch == "(":
            depth += 1
        elif not quote and ch == ")":
            depth -= 1
            if depth == 0 and i < len(t) - 1:
                return t, False                 # "(a) OR (b)": not one group
    return t[1:-1].strip(), True


def clean_planned_query(query: str) -> tuple[str, list[str]]:
    """Deterministic hygiene for a PLANNED query (the planner without thinking
    wrote sloppy Booleans, benchmark 2026-10-16): put quotes around bare
    multi-word terms inside OR groups (Europe PMC would AND their words), and
    drop facets made only of debate words. Well-formed queries come back
    unchanged. Explicit queries from a question file are never touched."""
    notes: list[str] = []
    facets_out = []
    for facet in _split_top(query, "AND"):
        inner, had_parens = _strip_parens(facet)
        alts = _split_top(inner, "OR")
        fixed = []
        for alt in alts:
            bare = (" " in alt and '"' not in alt and "(" not in alt and ":" not in alt
                    and "*" not in alt and not re.search(r"\b(?:AND|OR|NOT)\b", alt))
            if bare:
                notes.append(f"quoted {alt!r}")
                alt = f'"{alt}"'
            fixed.append(alt)
        words = {a.strip('"').lower() for a in fixed}
        if (words & META_TERMS) and words <= META_TERMS | META_COMPANIONS:
            notes.append(f"dropped debate facet {facet!r}")
            continue
        if len(fixed) > 1:
            facets_out.append("(" + " OR ".join(fixed) + ")")
        else:
            facets_out.append(f"({fixed[0]})" if had_parens else fixed[0])
    if len([f for f in facets_out if "SRC:MED" not in f.upper()]) == 0:
        return query, []                      # never strip a query down to nothing
    return " AND ".join(facets_out), notes


def resolve_queries(q: dict, cfg: dict, profile_text: str | None = None) -> list[str]:
    if q["explicit_query"]:
        print("query: explicit (from question file, deterministic)")
        queries = [q["explicit_query"]]
    else:
        print("query: none in file, planning via LLM (Hybrid fallback)")
        queries = plan_queries(q, cfg)
        if not queries:
            raise PraxisError("query planning produced no usable search query; "
                              "try rephrasing the question or add an explicit query")
        cleaned = []
        for query in queries:
            new, notes = clean_planned_query(query)
            for n in notes:
                print(f"  query clean-up: {n}")
            if new not in cleaned:            # a dropped facet can make two equal
                cleaned.append(new)
        queries = cleaned
    # Code enforces what a prompt could only suggest: no bare ambiguous
    # abbreviation reaches the search, planned or explicit.
    amb = parse_ambiguous(profile_text if profile_text is not None
                          else PROFILE.read_text(encoding="utf-8"))
    out = []
    for query in queries:
        new, changed = rewrite_ambiguous(query, amb)
        if changed:
            print(f"  expanded ambiguous abbreviation(s) {sorted(set(changed))} "
                  f"in the query")
        out.append(new)
    return out


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
        t = time.perf_counter()
        results = fetch.search_topic(query, ALL_TIME_START, end, ua,
                                     sort=PRAXIS_SORT, page_size=PRAXIS_PAGE_SIZE,
                                     timeout=PRAXIS_SEARCH_TIMEOUT)
        print(f"  q{i+1}: {len(results)} hits in {time.perf_counter() - t:.1f}s  "
              f"|  {query[:70]}")
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


THIN_FLOOR = 5               # fewer on-subject papers: code-set "thin evidence" note
CONTEXT_GUIDELINES_MAX = 3   # off-subject cardiac guidelines allowed as context
CONTEXT_NOTE = ("Kontext-Leitlinie: behandelt das Thema der Frage nicht direkt. "
                "Nur als allgemeinen Rahmen nutzen, nie als Beleg für die konkrete Frage.")


def is_context_guideline(c: dict, domain: dict) -> bool:
    """Off-subject, but a guideline in her field: broad guidelines often never
    name the specific condition (2024 EACTS CPB guideline for an HIT question)."""
    # Its title must also name a query concept (rank_all's title_relevance):
    # cardiac MeSH alone let in a coronary-dissection statement and preclinical
    # rigor guidelines (retrieval replay 2026-10-16).
    return (not c["on_subject"]
            and rank.study_type_label(c.get("pubTypes", [])) == "Leitlinie"
            and _mesh_hit(c.get("mesh") or [], domain["cardiac"])
            and (c.get("score_breakdown") or {}).get("title_relevance", 0) > 0)


def select_papers(ranked: list[dict], max_items: int, domain: dict) -> list[dict]:
    """On-subject papers only, no padding with off-subject ones (benchmark
    2026-10-16: padding filled all 20 slots of the HIT dossier with unrelated
    reviews). Exception: up to CONTEXT_GUIDELINES_MAX cardiac guidelines as
    marked context; they take the last slots. Zero on-subject papers: no
    dossier, a visible failure beats a confident answer from unrelated papers."""
    on = [r for r in ranked if r["on_subject"]]
    if not on:
        raise PraxisError(f"keine Paper zum Thema der Frage gefunden (0 von "
                          f"{len(ranked)} Kandidaten nennen das Subjekt der Suche)")
    ctx = [r for r in ranked if is_context_guideline(r, domain)][:CONTEXT_GUIDELINES_MAX]
    for r in ctx:
        r["context_guideline"] = True
    return on[: max(1, max_items - len(ctx))] + ctx


def praxis_payload(c: dict) -> dict:
    """What the synthesis sees per paper: the shared payload, plus a marker for
    context guidelines. Used by build_user AND evidence_record, so the evidence
    file holds exactly what the model got."""
    p = synth.paper_payload(c)
    if c.get("context_guideline"):
        p["bezug"] = CONTEXT_NOTE
    return p


def _flat(text: str) -> str:
    """Lowercase, hyphens/dashes as spaces, single spaces: for term matching."""
    return re.sub(r"\s+", " ", re.sub(r"[-‐‑–—/]", " ", (text or "").lower())).strip()


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
        # Hyphens and spacing are normalised on both sides: the query says
        # "heparin induced thrombocytopenia", abstracts say "heparin-induced"
        # (HIT benchmark 2026-10-16: a plain substring test failed every paper).
        hay = _flat(f"{c.get('title','')} {c.get('abstract','')}")
        item["on_subject"] = (not subj) or any(
            t in hay or (t.endswith("s") and t[:-1] in hay)
            for t in (_flat(s) for s in subj))
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
    t0 = time.perf_counter()
    oa_done = ft_done = 0.0
    with concurrent.futures.ThreadPoolExecutor(max_workers=ENRICH_MAX_WORKERS) as ex:
        oa_futures = {ex.submit(_oa_lookup, c, email, ua): c for c in oa_jobs}
        ft_futures = {ex.submit(_fulltext_lookup, c, ua): c for c in ft_jobs}
        for fut in concurrent.futures.as_completed(oa_futures):
            u = fut.result()
            if u:
                oa_futures[fut]["oaUrl"] = u
                oa += 1
        oa_done = time.perf_counter() - t0
        for fut in concurrent.futures.as_completed(ft_futures):
            x = fut.result()
            if x:
                ft_futures[fut]["fullTextExcerpt"] = x
                ft += 1
        ft_done = time.perf_counter() - t0
    print(f"  enriched top {len(selected)}: +{oa} OA links ({len(oa_jobs)} tried, "
          f"done at {oa_done:.1f}s), +{ft} full-text ({len(ft_jobs)} tried, done at "
          f"{ft_done:.1f}s)")


# --------------------------------------------------------------------------- #
# synthesis + deterministic assembly
# --------------------------------------------------------------------------- #
def build_user(q: dict, selected: list[dict]) -> str:
    papers = [praxis_payload(c) for c in selected]
    n_on = sum(1 for c in selected if c.get("on_subject", True))
    thin = (f"HINWEIS: Nur {n_on} der gelieferten Paper behandeln das Thema der Frage "
            "direkt. Sag in der Kurzantwort, dass die Evidenzbasis dünn ist, und "
            "fülle keine Lücken.\n\n") if n_on < THIN_FLOOR else ""
    return (
        f"FRAGE (rahmt das Dossier):\n{q['frage']}\n\n"
        + (f"KONTEXT:\n{q['kontext']}\n\n" if q["kontext"] else "")
        + thin
        + "Hier sind die gerankten Paper als JSON (evidence_basis = Volltext-"
        "Auszug oder Abstract). Schreibe das Dossier exakt nach dem Vertrag im "
        "System-Prompt. Belege tragende Aussagen inline mit "
        "`(PMID <pmid>: \"woertlich kopiertes Zitat aus evidence_basis\")` aus den "
        "mitgelieferten PMIDs; jede Zahl der Aussage muss im Zitat stehen. "
        "Schreibe KEINE Stufe-, Provenienz- oder "
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
    n_on = sum(1 for c in selected if c.get("on_subject", True))
    if n_on < THIN_FLOOR:
        # Code-set, like Stufe and provenance: the model cannot drop it.
        heading += (f"\n> Hinweis: Nur {n_on} der gefundenen Paper behandeln das Thema "
                    f"der Frage direkt. Die Evidenzbasis ist dünn; wichtige Arbeiten "
                    f"können fehlen.\n")
    such =("## Verwendete Suchanfrage\n\n"
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
    `synthesis_raw` is the model prose before finalize, WITH its quote anchors,
    so model output and code-added parts stay separable. `anchors` lists each
    (pmid, quote) and whether code found the quote in that paper's text."""
    basis = {str(c.get("pmid")): synth.paper_payload(c)["evidence_basis"]
             for c in selected}
    anchors = [{"pmid": p, "quote": qt,
                "in_source": check_claims.find_quote(qt, basis.get(p, ""))}
               for a in check_claims.split_anchors(body)[2] for p, qt in a["quotes"]]
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "reconstructed": False,
        "question": {"title": q.get("title"), "frage": q.get("frage"),
                     "kontext": q.get("kontext")},
        "queries": queries,
        "synthesis_raw": body,
        "anchors": anchors,
        "papers": [{**praxis_payload(c),
                    "provenance": synth.provenance(c),
                    "on_subject": c.get("on_subject"),
                    "context_guideline": bool(c.get("context_guideline")),
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
    # Per-stage wall time (seconds), printed at the end and kept in the evidence
    # file, so "where do the 90 s go" is measured, not guessed.
    timings: dict[str, float] = {}
    t0 = t = time.perf_counter()
    queries = resolve_queries(q, cfg, profile_text)
    timings["plan"] = time.perf_counter() - t
    for query in queries:
        print(f"  -> {query}")
    yield ("queries", {"queries": queries})

    print("\n=== fetch (all-time) ===")
    t = time.perf_counter()
    cands = run_search(queries, ua)
    timings["search"] = time.perf_counter() - t
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
    t = time.perf_counter()
    ranked = rank_all(cands, profile_text, queries, domain)
    selected = select_papers(ranked, q["max_items"], domain)
    timings["rank"] = time.perf_counter() - t
    n_on = sum(1 for s in selected if s["on_subject"])
    n_ctx = len(selected) - n_on
    print(f"  ranked {len(ranked)} ({sum(r['on_subject'] for r in ranked)} on-subject), "
          f"selected {len(selected)}"
          + (f", incl. {n_ctx} context guideline(s)" if n_ctx else "")
          + (f"  THIN: only {n_on} on-subject" if n_on < THIN_FLOOR else ""))
    for s in selected[:10]:
        flag = " " if s["on_subject"] else "~"     # ~ marks a context guideline
        print(f"   {flag}Stufe {s['stufe']}  score {s['score']:>6}  "
              f"{(s.get('journalAbbrev') or '?')[:24]:<24}  {(s.get('title') or '')[:44]}")

    print("\n=== enrich (top N) ===")
    t = time.perf_counter()
    enrich_top(selected, ua, contact)
    timings["enrich"] = time.perf_counter() - t
    yield ("selected", {"selected": selected, "count": len(selected)})

    print("\n=== synthesize (one LLM call) ===")
    t = time.perf_counter()
    raw = synthesize_dossier(q, selected, cfg, profile_text)
    timings["synthesis"] = time.perf_counter() - t
    if raw is None:
        raise PraxisError("no provider produced a dossier (missing keys, errors, "
                          "or refusals)")
    # Quote anchors come off FIRST: before validation, before the web stream
    # sees the prose, before finalize strips dashes (source quotes contain en
    # dashes and must stay verbatim). The raw form goes to evidence.json only.
    body, _, anchors = check_claims.split_anchors(raw)
    leaks = check_claims.quote_leaks(body)
    if leaks:
        # Safety net: never show source quotes to the reader, even in a format
        # the parser does not know. Cut from the colon to the end of the group.
        print(f"  WARN: {len(leaks)} unparsed quote anchor(s); stripped from the "
              f"shown text", file=sys.stderr)
        body = re.sub(r'(\(\s*PMID\s*:?\s*\d{5,9})\s*:\s*["“„”][^\n]*?\)(?=[\s.,;]|$)',
                      r"\1)", body)
    if not anchors:
        print("  WARN: no quote anchors in the dossier; the contract requires "
              "(PMID ...: \"quote\") on load-bearing claims", file=sys.stderr)
    validate_citations(body, selected)
    scan_dose_directives(body)
    yield ("synthesis", {"text": body})

    dossier = finalize(body, queries, selected, q)
    if enforce_limit:
        record_dossier()      # count only on success, after synthesis spend
    timings["total"] = time.perf_counter() - t0
    print("  timing: " + " | ".join(f"{k} {v:.1f}s" for k, v in timings.items()))
    evidence = evidence_record(q, queries, selected, raw)
    evidence["timings"] = {k: round(v, 2) for k, v in timings.items()}
    yield ("done", {"dossier": dossier, "queries": queries, "selected": selected,
                    "evidence": evidence})


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
