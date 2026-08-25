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
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

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
PROFILE = ROOT / "profil" / "profile.md"
KANON = ROOT / "profil" / "kanon.md"

ALL_TIME_START = "1900-01-01"   # disables the weekly window: landmark trials included
PRAXIS_SORT = "CITED desc"      # most-cited first, so landmark papers surface all-time
PRAXIS_PAGE_SIZE = 200          # deep pool: landmarks sit far down the citation ranking,
                                #   so a 50-wide pool would never fetch them
DEFAULT_MAX_ITEMS = 20
MAX_PLANNED_QUERIES = 3
TITLE_HIT_WEIGHT = 40           # per query concept found in a paper's TITLE
TITLE_HIT_CAP = 3               # bonus caps at 3 hits (+120), enough to lift an
                                #   on-topic RCT over an off-topic but highly-cited guideline
STOP_TOKENS = {"and", "or", "not", "src", "med", "first", "pdate"}


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


# --------------------------------------------------------------------------- #
# provider calls (reuse synthesize's provider seam for BOTH planning + dossier)
# --------------------------------------------------------------------------- #
def call_llm(system: str, user: str, cfg: dict, purpose: str) -> str:
    """Run the configured provider order (primary, then fallback). Returns the
    text, or '' if every provider missed / errored / refused."""
    order = [cfg["primary"]] + ([cfg["fallback"]] if cfg["fallback"] else [])
    for name in order:
        r = synth.run_provider(name, system, user, cfg)
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
    text = call_llm(PLAN_SYSTEM, user, cfg, "query-planung")
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
        raise SystemExit("query planning produced nothing and no explicit query "
                         "was given; add a ```query block to the question file.")
    return planned


# --------------------------------------------------------------------------- #
# search + rank + enrich (reused slice-1 functions, composed here)
# --------------------------------------------------------------------------- #
def run_search(queries: list[str], ua: str) -> list[dict]:
    end = date.today().isoformat()
    by_key: dict[str, dict] = {}
    for i, query in enumerate(queries):
        results = fetch.search_topic(query, ALL_TIME_START, end, ua,
                                     sort=PRAXIS_SORT, page_size=PRAXIS_PAGE_SIZE)
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
                by_key[key] = fetch.normalise(rec, [label])
        time.sleep(0.25)
    return list(by_key.values())


def query_concepts(queries: list[str]) -> set[str]:
    """Salient topic terms from the resolved query: quoted phrases plus bare
    tokens, minus boolean/field operators and wildcards. Used to score how
    on-topic a paper's TITLE is (a citation-sorted all-time pool otherwise floats
    famous but off-topic papers that match the broad OR terms only in passing)."""
    terms: set[str] = set()
    for q in queries:
        for phrase in re.findall(r'"([^"]+)"', q):
            terms.add(phrase.lower().strip())
        bare = re.sub(r'"[^"]+"', " ", q)          # drop quoted spans first
        for tok in re.findall(r"[A-Za-z][A-Za-z-]{3,}", bare):
            t = tok.lower().rstrip("*")
            if t not in STOP_TOKENS:
                terms.add(t)
    return terms


def title_bonus(cand: dict, concepts: set[str]) -> int:
    title = (cand.get("title") or "").lower()
    hits = sum(1 for t in concepts if t in title)
    return min(hits, TITLE_HIT_CAP) * TITLE_HIT_WEIGHT


def rank_all(cands: list[dict], profile_text: str,
             queries: list[str]) -> list[dict]:
    prof = rank.parse_profile(profile_text)
    kanon_kw = rank.kanon_keywords(KANON)
    concepts = query_concepts(queries)
    today = date.today()
    ranked = []
    for c in cands:
        stufe = rank.evidence_level(c.get("pubTypes", []))
        total, breakdown = rank.score(c, stufe, prof["trust"], kanon_kw, today)
        tb = title_bonus(c, concepts)              # Praxis-only topical relevance
        total += tb
        breakdown["title_relevance"] = tb
        item = dict(c)
        item["stufe"] = stufe
        item["score"] = round(total, 1)
        item["score_breakdown"] = breakdown
        ranked.append(item)
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


def enrich_top(selected: list[dict], ua: str, email: str) -> None:
    """OA link + full-text excerpt for the selected papers only (in place). The
    corpus is large, so enrich AFTER ranking, not before."""
    oa = ft = 0
    for c in selected:
        if c.get("doi") and not c.get("oaUrl"):
            try:
                u = enrich.unpaywall_oa_url(c["doi"], email, ua)
            except Exception as e:
                print(f"  unpaywall error {c['doi']}: {e}", file=sys.stderr)
                u = None
            if u:
                c["oaUrl"] = u
                oa += 1
            time.sleep(0.2)
        if c.get("pmcid") and not c.get("fullTextExcerpt"):
            try:
                x = enrich.fulltext_excerpt(c["pmcid"], ua)
            except Exception as e:
                print(f"  fulltext error {c['pmcid']}: {e}", file=sys.stderr)
                x = None
            if x:
                c["fullTextExcerpt"] = x
                ft += 1
            time.sleep(0.2)
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
    unknown = cited - known
    if unknown:
        print(f"  WARN: dossier cites {len(unknown)} PMID(s) not in the selected "
              f"set (possible hallucination): {sorted(unknown)}", file=sys.stderr)


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
# main
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
    cfg = synth.parse_synthese_config(profile_text)
    contact = fetch.parse_profile(profile_text)["contact_email"] or "unknown@example.com"
    ua = f"journal-watch/0.1 (+{contact})"

    q = parse_question(pick_question(args.frage))
    print(f"question: {q['path'].name}  |  max_items={q['max_items']}")
    print(f"title: {q['title']}")

    queries = resolve_queries(q, cfg)
    for query in queries:
        print(f"  -> {query}")
    if args.plan_only:
        return 0

    print("\n=== fetch (all-time) ===")
    cands = run_search(queries, ua)
    print(f"  {len(cands)} unique candidates")
    if not cands:
        print("no candidates found for this question.", file=sys.stderr)
        return 1

    print("\n=== rank (all-time, recency as bonus) ===")
    ranked = rank_all(cands, profile_text, queries)
    selected = ranked[: q["max_items"]]
    print(f"  ranked {len(ranked)}, selected top {len(selected)}")
    for s in selected[:10]:
        print(f"    Stufe {s['stufe']}  score {s['score']:>6}  "
              f"{(s.get('journalAbbrev') or '?')[:24]:<24}  {(s.get('title') or '')[:44]}")

    print("\n=== enrich (top N) ===")
    enrich_top(selected, ua, contact)

    print("\n=== synthesize (one LLM call) ===")
    body = synthesize_dossier(q, selected, cfg, profile_text)
    if body is None:
        print("No provider produced a dossier (missing keys, errors, refusals).",
              file=sys.stderr)
        return 1
    validate_citations(body, selected)
    dossier = finalize(body, queries, selected, q)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Strip a leading YYYY-MM-DD from the slug so a dated question filename does
    # not double the date in the dossier name.
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", q["slug"])
    out = OUTPUT / f"{date.today().isoformat()}-{slug}.md"
    out.write_text(dossier, encoding="utf-8")
    print(f"\nwrote dossier -> {out}")

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
