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
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
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
]


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
            queries = pc.resolve_queries(q, cfg)
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
            return pc.build_dossier(q, profile_text=profile_text)
        except pc.PraxisError:
            raise                       # a real "no candidates" is not retryable
        except Exception as e:          # network/transport blips are
            if i == attempts:
                raise
            wait = 3 * i
            print(f"  transient error ({type(e).__name__}: {e}); "
                  f"retry {i}/{attempts-1} in {wait}s")
            time.sleep(wait)


def full_run(profile_text: str) -> None:
    rows = []
    for item in QUESTIONS:
        q = as_q(item)
        print(f"\n{'='*70}\n{item['tag']}  |  {item['title']}\n{'='*70}")
        try:
            res = build_with_retry(q, profile_text)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            rows.append((item["tag"], "FAILED", "", "", "", "", "", ""))
            continue

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
                     "yes" if len(controversy) > 120 else "THIN", words))
        print(f"  offsub {offsub}/{total} | tiers 1/2/3 "
              f"{tiers[1]}/{tiers[2]}/{tiers[3]}"
              f" | cited {len(cited)} phantom {phantom} | dose-directives {dose_hits}"
              f" | controversy {'yes' if len(controversy) > 120 else 'THIN'}"
              f" | {words} body words")

    print(f"\n\n{'='*90}\nSUMMARY\n{'='*90}")
    print(f"{'tag':<24} {'offsub':>7} {'tiers123':>9} {'cited':>6} {'phantom':>8} "
          f"{'dose':>5} {'controv':>8} {'words':>6}")
    for r in rows:
        print(f"{r[0]:<24} {str(r[1]):>7} {str(r[2]):>9} {str(r[3]):>6} "
              f"{str(r[4]):>8} {str(r[5]):>5} {str(r[6]):>8} {str(r[7]):>6}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Praxis-Check benchmark harness.")
    ap.add_argument("--plan-only", action="store_true",
                    help="cheap: resolve queries only, report breadth")
    args = ap.parse_args(argv)
    profile_text = pc.PROFILE.read_text(encoding="utf-8")
    if args.plan_only:
        plan_only(profile_text)
    else:
        full_run(profile_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
