#!/usr/bin/env python3
"""Benchmark harness for the Praxis-Check.

Runs a fixed set of cardiac-anaesthesia questions (her real domain, from
interview 1) through the SAME build_dossier core the CLI and web app use, and
captures deterministic metrics so we can spot patterns across questions instead
of eyeballing one dossier. Two modes:

  python scripts/benchmark_praxis.py --plan-only   # cheap: 1 planner call/question,
                                                   #   reports query breadth only
  python scripts/benchmark_praxis.py               # full: build_dossier/question,
                                                   #   reports leak/tier/attribution/...

Questions live inline (not in fragen/) so the benchmark never pollutes her real
question flow or the CLI's newest-file default pick.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_claims as cc
import praxis_check as pc
import synthesize as synth

# Her domain, her shape (Evidenz / Standard / Kontroverse). Tags mark what each
# question is meant to stress.
QUESTIONS = [
    dict(tag="pilot/controversy",
         title="Kortikosteroide und Timing um das Loesen der Aortenklemme",
         frage=("Welche Evidenz gibt es zur Gabe von Kortikosteroiden und zum "
                "Timing der Medikamentengabe rund um das Loesen der Aortenklemme "
                "(Reperfusion) in der Herzchirurgie? Wo ist sich die "
                "Fachgemeinschaft uneins?")),
    dict(tag="controversy/overlap-generic",
         title="Volatile Anaesthetika vs. TIVA zur Myokardprotektion",
         frage=("Volatile Anaesthetika versus totale intravenoese Anaesthesie "
                "mit Propofol zur Myokardprotektion bei kardiochirurgischen "
                "Eingriffen mit Herz-Lungen-Maschine: was zeigt die Evidenz zum "
                "Outcome?")),
    dict(tag="dose-trap/controversy",
         title="Tranexamsaeure-Dosierung in der Herzchirurgie",
         frage=("Hochdosis- versus Niedrigdosis-Tranexamsaeure in der "
                "Herzchirurgie: Wirksamkeit gegen Blutungen versus "
                "Krampfanfallrisiko. Was ist Standard und wo ist die "
                "Literatur uneins?")),
    dict(tag="volume/controversy",
         title="Dexmedetomidin gegen Delir und Vorhofflimmern nach Herz-OP",
         frage=("Dexmedetomidin zur Praevention von postoperativem Delir und "
                "Vorhofflimmern nach herzchirurgischen Eingriffen: aktuelle "
                "Evidenzlage.")),
    dict(tag="precision/device-leak",
         title="Zerebrale Oximetrie (NIRS) in der Herzchirurgie",
         frage=("Verbessert intraoperatives Monitoring mit zerebraler Oximetrie "
                "(NIRS) das neurologische Outcome bei herzchirurgischen "
                "Patienten?")),
    dict(tag="leak-prone/adjacency",
         title="Sugammadex vs. Neostigmin in der Herzchirurgie",
         frage=("Sugammadex versus Neostigmin zur Antagonisierung der "
                "neuromuskulaeren Blockade bei herzchirurgischen Patienten: "
                "Evidenz und Standard.")),
    dict(tag="boundary/surgical",
         title="Del-Nido- vs. Blutkardioplegie bei Erwachsenen",
         frage=("Del-Nido-Kardioplegie versus konventionelle Blutkardioplegie "
                "bei erwachsenen Patienten in der Herzchirurgie: was zeigt die "
                "Evidenz zum Outcome?")),
    # Added 2026-10-16: the fictional Replit simulation (urgent CABG, acute HIT)
    # where real citations carried a wrong denominator (CHOOSE-ON 43 vs 46/49).
    dict(tag="numbers/hit-cabg",
         title="Alternative Antikoagulation bei akuter HIT und dringlicher Bypass-OP",
         frage=("Welche Evidenz gibt es zur Antikoagulation mit Alternativen zu "
                "Heparin bei akuter heparininduzierter Thrombozytopenie (HIT), wenn "
                "eine dringliche Bypass-Operation mit Herz-Lungen-Maschine noetig "
                "ist? Wie unterscheidet sich das Vorgehen bei akuter HIT von einer "
                "frueheren, abgeklungenen HIT?")),
]

# A/B gate (05_praxis-check/PLAN-quote-anchoring.md): option A (quote rule in
# the contract) holds only if the model anchors and quotes reliably enough.
GATE_QUOTED = 0.95      # share of cited claims that carry a quote
GATE_VERBATIM = 0.90    # share of quotes found word for word in their paper
RUNS = pc.STAGE / "benchmark-runs"


def as_q(item: dict) -> dict:
    """Turn a benchmark item into the question dict build_dossier expects."""
    return {"path": None, "slug": pc._slugify(item["title"]),
            "title": item["title"], "frage": item["frage"], "kontext": "",
            "max_items": pc.DEFAULT_MAX_ITEMS, "explicit_query": ""}


def and_facets(query: str) -> int:
    """Count top-level AND facets as a narrowness proxy (each AND is one more
    concept the paper must satisfy; the CLI's too-narrow queries had many)."""
    return len(re.findall(r"\bAND\b", query, re.I))


def plan_only(profile_text: str) -> None:
    cfg = synth.parse_synthese_config(profile_text)
    print(f"{'tag':<24} {'#q':>3} {'AND/q':>6} {'concepts':>9}  title")
    print("-" * 90)
    for item in QUESTIONS:
        q = as_q(item)
        try:
            queries = pc.resolve_queries(q, cfg, profile_text)
        except pc.PraxisError as e:
            print(f"{item['tag']:<24}  PLAN FAILED: {e}")
            continue
        facets = [and_facets(x) for x in queries]
        avg_and = sum(facets) / len(facets) if facets else 0
        concepts = pc.query_concepts(queries)
        print(f"{item['tag']:<24} {len(queries):>3} {avg_and:>6.1f} "
              f"{len(concepts):>9}  {item['title'][:34]}")
        for x in queries:
            print(f"    ({and_facets(x)} AND) {x[:110]}")
    print("\nplan-only: narrowness = AND/q. High AND count starves retrieval "
          "(the single-question CLI run had 6-7 ANDs and only 3-16 hits).")


def offsubject_rate(selected: list[dict]) -> tuple[int, int]:
    """Selected papers that failed the subject-actor gate (mention only the broad
    context, not the intervention). This is the sharpened leak measure: the old
    any-concept test scored these as on-topic because "cardiac surgery" is a
    concept. Reads the on_subject flag rank_all now sets. Returns (offsub, total)."""
    offsub = sum(1 for c in selected if not c.get("on_subject", True))
    return offsub, len(selected)


def body_words(dossier: str) -> int:
    """Word count of the prose body only, cutting the appended apparatus
    (Verwendete Suchanfrage + Quellen) so the ~20-item source list does not
    inflate the point-of-care length metric."""
    body = re.split(r"\n##\s+(?:Verwendete Suchanfrage|Quellen)\b", dossier)[0]
    return len(re.findall(r"\w+", body))


def build_with_retry(q: dict, profile_text: str, attempts: int = 3):
    """Benchmark-only resilience: Europe PMC occasionally drops a connection
    (RemoteDisconnected). Retry with backoff so one transient blip does not kill
    the whole batch. Pipeline code stays untouched; this wrapper lives here."""
    for i in range(1, attempts + 1):
        try:
            return pc.build_dossier(q, profile_text=profile_text,
                                    enforce_limit=False)  # eval never eats quota
        except pc.PraxisError:
            raise                       # a real "no candidates" is not retryable
        except Exception as e:          # network/transport blips are
            if i == attempts:
                raise
            wait = 3 * i
            print(f"  transient error ({type(e).__name__}: {e}); "
                  f"retry {i}/{attempts-1} in {wait}s")
            time.sleep(wait)


def save_run(out_dir: Path, q: dict, res) -> Path:
    """Freeze each benchmark dossier with the evidence the model saw, so it can
    be re-checked or replayed later without another API call."""
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"{q['slug']}.md"
    if md.exists():
        # Never overwrite a frozen run: a same-day rerun of one question
        # destroyed the original HIT run on 2026-10-16.
        md = out_dir / f"{q['slug']}-{time.strftime('%H%M%S')}.md"
    md.write_text(res.dossier, encoding="utf-8")
    pc.evidence_path(md).write_text(
        json.dumps(res.evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return md


def recheck(run_dir: Path) -> None:
    """No API calls: re-run the claim checker and the gate over saved runs, so a
    checker fix can be measured on the same frozen model output."""
    tot = {"cited_claims": 0, "quoted_claims": 0, "quotes": 0, "verbatim": 0}
    for md in sorted(run_dir.glob("*.md")):
        ev_path = pc.evidence_path(md)
        if not ev_path.exists():
            continue
        evd = json.loads(ev_path.read_text(encoding="utf-8"))
        findings, met = cc.check_with_metrics(md.read_text(encoding="utf-8"), evd)
        for k in tot:
            tot[k] += met[k]
        fails = sum(f.level == "FAIL" for f in findings)
        print(f"{md.stem[:48]:<48} anchored {met['quoted_claims']}/{met['cited_claims']}"
              f"  verbatim {met['verbatim']}/{met['quotes']}  claim FAILs {fails}")
    print(gate_verdict(tot))


BARE_ABBR = re.compile(r"\b[A-Z][A-Z0-9]{1,4}\b")
QUERY_WORDS = {"AND", "OR", "NOT", "SRC", "MED"}


def replay_retrieval(run_dir: Path, profile_text: str) -> None:
    """No LLM call: take the planner queries frozen in each saved run, apply
    today's query rewrite, and run today's search, gates and selection against
    live Europe PMC. Shows what the retrieval changes do to the same queries.
    Also lists bare short abbreviations left in the queries, for the
    ambiguity list in profile.md."""
    amb = pc.parse_ambiguous(profile_text)
    domain = pc.parse_domain(profile_text)
    contact = pc.fetch.parse_profile(profile_text)["contact_email"] or "unknown@example.com"
    ua = f"journal-watch/0.1 (+{contact})"
    print(f"{'run':<44} {'before':>8} {'after':>8} {'ctx':>4}  note")
    for ev_path in sorted(run_dir.glob("*.evidence.json")):
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        name = ev_path.name.replace(".evidence.json", "")[:44]
        before = sum(1 for p in ev["papers"] if p.get("on_subject"))
        queries, changed, cleaned = [], [], 0
        for q in ev["queries"]:                 # frozen queries are planner output
            new, notes = pc.clean_planned_query(q)
            cleaned += bool(notes)
            new, ch = pc.rewrite_ambiguous(new, amb)
            if new not in queries:
                queries.append(new)
            changed += ch
        bare = sorted({t for q in queries for part in re.split(r'"[^"]*"', q)
                       for t in BARE_ABBR.findall(part)} - QUERY_WORDS)
        cands = [c for c in pc.run_search(queries, ua)
                 if not pc.is_retracted(c.get("pubTypes", []))
                 and not pc.off_domain(c, domain)]
        ranked = pc.rank_all(cands, profile_text, queries, domain)
        try:
            sel = pc.select_papers(ranked, pc.DEFAULT_MAX_ITEMS, domain)
            on = sum(1 for s in sel if s["on_subject"])
            ctx = len(sel) - on
            after = f"{on}/{len(sel)}"
        except pc.PraxisError:
            sel, ctx, after = [], 0, "0 -> stop"
        note = []
        if cleaned:
            note.append(f"cleaned {cleaned} of {len(ev['queries'])} queries")
        if changed:
            note.append(f"expanded {sorted(set(changed))}")
        if bare:
            note.append(f"bare abbr left: {bare}")
        print(f"{name:<44} {before:>5}/{len(ev['papers']):<2} {after:>8} {ctx:>4}  "
              + "; ".join(note))
        for s in sel[:6]:
            print(f"      {'~' if not s['on_subject'] else ' '} {(s.get('title') or '')[:90]}")


def full_run(profile_text: str, only: list[str] | None = None,
             label: str | None = None) -> None:
    rows = []
    tot = {"cited_claims": 0, "quoted_claims": 0, "quotes": 0, "verbatim": 0}
    out_dir = RUNS / date.today().isoformat()
    if label:
        out_dir = out_dir / label            # keep experiment runs apart
    questions = [q for q in QUESTIONS if not only or any(o in q["tag"] for o in only)]
    for item in questions:
        q = as_q(item)
        print(f"\n{'='*70}\n{item['tag']}  |  {item['title']}\n{'='*70}")
        t0 = time.time()
        try:
            res = build_with_retry(q, profile_text)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            rows.append((item["tag"], "FAILED", "", "", "", "", "", "", "", "", "", ""))
            continue
        secs = time.time() - t0
        print(f"  saved -> {save_run(out_dir, q, res)}")
        findings, met = cc.check_with_metrics(res.dossier, res.evidence or {})
        for k in tot:
            tot[k] += met[k]
        claim_fails = sum(f.level == "FAIL" for f in findings)
        anch = f"{met['quoted_claims']}/{met['cited_claims']}"
        verb = f"{met['verbatim']}/{met['quotes']}"

        offsub, total = offsubject_rate(res.selected)
        tiers = {1: 0, 2: 0, 3: 0}
        for c in res.selected:
            tiers[c.get("stufe", 3)] += 1

        # attribution: cited PMIDs vs the pool; unknown = phantom
        known = {str(c["pmid"]) for c in res.selected if c.get("pmid")}
        cited = set(re.findall(r"\d+", " ".join(
            re.findall(r"\(PMID\s+([\d,\s]+)\)", res.dossier))))
        phantom = len(cited - known)

        dose_hits = len(pc.DOSE_DIRECTIVE.findall(res.dossier))
        controversy = pc._section(res.dossier, "Wo die Literatur uneins ist")
        words = body_words(res.dossier)

        rows.append((item["tag"], f"{offsub}/{total}",
                     f"{tiers[1]}/{tiers[2]}/{tiers[3]}",
                     len(cited), phantom, dose_hits,
                     "yes" if len(controversy) > 120 else "THIN", words,
                     anch, verb, claim_fails, f"{secs:.0f}s"))
        print(f"  offsub {offsub}/{total} | tiers 1/2/3 "
              f"{tiers[1]}/{tiers[2]}/{tiers[3]}"
              f" | cited {len(cited)} phantom {phantom} | dose-directives {dose_hits}"
              f" | controversy {'yes' if len(controversy) > 120 else 'THIN'}"
              f" | {words} body words")
        print(f"  anchored {anch} | verbatim {verb} | claim-check FAILs {claim_fails}"
              f" | {secs:.0f}s")

    print(f"\n\n{'='*110}\nSUMMARY\n{'='*110}")
    print(f"{'tag':<24} {'offsub':>7} {'tiers123':>9} {'cited':>6} {'phantom':>8} "
          f"{'dose':>5} {'controv':>8} {'words':>6} {'anchored':>9} {'verbatim':>9} "
          f"{'cfail':>6} {'time':>5}")
    for r in rows:
        print(f"{r[0]:<24} {str(r[1]):>7} {str(r[2]):>9} {str(r[3]):>6} "
              f"{str(r[4]):>8} {str(r[5]):>5} {str(r[6]):>8} {str(r[7]):>6} "
              f"{str(r[8]):>9} {str(r[9]):>9} {str(r[10]):>6} {str(r[11]):>5}")
    print(gate_verdict(tot))


def gate_verdict(tot: dict) -> str:
    """The A/B decision from PLAN-quote-anchoring.md, from summed counts."""
    if not tot["cited_claims"] or not tot["quotes"]:
        return "\nGATE: no anchored claims at all -> option A fails, build B (Claude Citations)."
    quoted = tot["quoted_claims"] / tot["cited_claims"]
    verbatim = tot["verbatim"] / tot["quotes"]
    holds = quoted >= GATE_QUOTED and verbatim >= GATE_VERBATIM
    return (f"\nGATE: quoted {quoted:.0%} (need {GATE_QUOTED:.0%}), verbatim "
            f"{verbatim:.0%} (need {GATE_VERBATIM:.0%}) -> "
            + ("option A holds." if holds else "option A misses: build B (Claude Citations)."))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Praxis-Check benchmark harness.")
    ap.add_argument("--plan-only", action="store_true",
                    help="cheap: resolve queries only, report breadth")
    ap.add_argument("--only", help="comma-separated tag substrings: run just these "
                    "questions (e.g. to redo the ones an outage killed)")
    ap.add_argument("--recheck", metavar="DIR", help="no API calls: re-check saved "
                    "runs in DIR (e.g. 05_praxis-check/benchmark-runs/2026-10-16)")
    ap.add_argument("--replay-retrieval", metavar="DIR", help="no LLM: re-run today's "
                    "search, gates and selection on the queries frozen in DIR")
    ap.add_argument("--label", help="save this run under benchmark-runs/<date>/<label>/")
    ap.add_argument("--thinking-planner", type=int, metavar="N",
                    help="Gemini thinking budget for the planner (0 = off), this run only")
    ap.add_argument("--thinking-synthesis", type=int, metavar="N",
                    help="Gemini thinking budget for the synthesis (0 = off), this run only")
    args = ap.parse_args(argv)
    if args.recheck:
        recheck(Path(args.recheck))
        return 0
    profile_text = pc.PROFILE.read_text(encoding="utf-8")
    # Experiment overrides: rewrite the field in memory, profile.md stays as is.
    for name, value in (("planer_thinking_gemini", args.thinking_planner),
                        ("synthese_thinking_gemini", args.thinking_synthesis)):
        if value is not None:
            profile_text = re.sub(rf"(`{name}`\s*:)[^\n#]*", rf"\g<1> {value} ",
                                  profile_text)
            print(f"override: {name} = {value}")
    if args.replay_retrieval:
        replay_retrieval(Path(args.replay_retrieval), profile_text)
        return 0
    if args.plan_only:
        plan_only(profile_text)
    else:
        full_run(profile_text, args.only.split(",") if args.only else None, args.label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
