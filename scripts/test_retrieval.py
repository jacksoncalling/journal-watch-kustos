#!/usr/bin/env python3
"""Tests for retrieval relevance (05_praxis-check/PLAN-retrieval-relevance.md).

Plain asserts, no framework, no network, no LLM: `python scripts/test_retrieval.py`.
Covers the three causes of the HIT benchmark failure (2026-10-16): bare
ambiguous abbreviations in the query, the hyphen blind spot in the subject
gate, and padding the selection with off-subject papers.
"""
from __future__ import annotations


import praxis_check as pc
import verify_dossier as vd

RESULTS: list[bool] = []
PROFILE = pc.PROFILE.read_text(encoding="utf-8")
AMB = pc.parse_ambiguous(PROFILE)
DOMAIN = pc.parse_domain(PROFILE)


def ok(cond: bool, note: str) -> None:
    print(f"  [{'ok ' if cond else 'FAIL'}] {note}")
    RESULTS.append(bool(cond))


def abbreviations() -> None:
    print("ambiguous abbreviations:")
    ok(AMB.get("HIT") == ["heparin-induced thrombocytopenia"], "profile lists HIT")
    q = '("heparin induced thrombocytopenia" OR HIT) AND (acute OR active) AND SRC:MED'
    new, changed = pc.rewrite_ambiguous(q, AMB)
    ok(' HIT' not in new and '"heparin-induced thrombocytopenia"' in new and changed == ["HIT"],
       "bare HIT (the live planner query) becomes the quoted phrase")
    new, _ = pc.rewrite_ambiguous('"HIT antibodies" AND hit-rate AND SHIT AND HIT2', AMB)
    ok(new == '"HIT antibodies" AND hit-rate AND SHIT AND HIT2',
       "quoted phrase, hyphen compound and longer words are left alone")
    new, _ = pc.rewrite_ambiguous("hit AND ACT AND SRC:MED", AMB)
    ok(new == '"heparin-induced thrombocytopenia" AND "activated clotting time" AND SRC:MED',
       "lower-case bare 'hit' and ACT are expanded too (search ignores case)")
    multi = {"PE": ["pulmonary embolism", "pleural effusion"]}
    ok(pc.rewrite_ambiguous("PE AND x", multi)[0]
       == '("pulmonary embolism" OR "pleural effusion") AND x',
       "several expansions become an OR group")
    q = {"explicit_query": "HIT AND bivalirudin AND SRC:MED", "frage": "", "kontext": ""}
    ok(pc.resolve_queries(q, {}, PROFILE)
       == ['"heparin-induced thrombocytopenia" AND bivalirudin AND SRC:MED'],
       "explicit queries from a question file are rewritten too")


def query_cleanup() -> None:
    print("planned-query clean-up:")
    sloppy = ("(corticosteroids OR steroids) AND (aortic cross-clamp OR reperfusion) AND "
              "(cardiac surgery OR heart surgery) AND (controversy OR conflicting evidence "
              "OR unresolved) AND SRC:MED")       # live planner, thinking off, 2026-10-16
    new, notes = pc.clean_planned_query(sloppy)
    ok(new == '(corticosteroids OR steroids) AND ("aortic cross-clamp" OR reperfusion) AND '
              '("cardiac surgery" OR "heart surgery") AND SRC:MED',
       "live sloppy query: phrases quoted, debate facet dropped")
    good = ('("heparin induced thrombocytopenia" OR "heparin-induced thrombocytopenia") AND '
            '(acute OR active) AND ("cardiopulmonary bypass" OR CPB) AND SRC:MED')
    ok(pc.clean_planned_query(good) == (good, []), "well-formed query comes back unchanged")
    ok(pc.clean_planned_query(new)[0] == new, "clean-up is idempotent")
    keep = '(dexamethasone) AND (guidelines OR recommendations) AND (controversy OR dexamethasone) AND SRC:MED'
    ok(pc.clean_planned_query(keep)[0] == keep,
       "guideline-only facet and a facet mixing debate and topic words are kept")
    odd = '(steroid* OR TITLE:"cardiac surgery") AND (a OR (b AND c d)) AND SRC:MED'
    ok(pc.clean_planned_query(odd)[0] == odd, "wildcards, field terms, nested groups untouched")
    ok(pc.clean_planned_query("(controversy OR debate) AND SRC:MED")[0]
       == "(controversy OR debate) AND SRC:MED", "never strips a query down to nothing")
    q = {"explicit_query": "(cardiac surgery) AND (controversy) AND SRC:MED",
         "frage": "", "kontext": ""}
    ok(pc.resolve_queries(q, {}, PROFILE) == ["(cardiac surgery) AND (controversy) AND SRC:MED"],
       "explicit queries from a question file are NOT cleaned (her wording)")
    orig = pc.plan_queries
    pc.plan_queries = lambda qq, cfg: [
        "(a OR b) AND (cardiac surgery) AND (debate OR controversy) AND SRC:MED",
        '(a OR b) AND ("cardiac surgery") AND SRC:MED']
    try:
        out = pc.resolve_queries({"explicit_query": "", "frage": "", "kontext": ""}, {}, PROFILE)
    finally:
        pc.plan_queries = orig
    ok(out == ['(a OR b) AND ("cardiac surgery") AND SRC:MED'],
       "planned queries are cleaned, and duplicates after clean-up are merged")


def cand(pmid: str, title: str, abstract: str = "", pub=("Journal Article",),
         mesh=(), cites: int = 0) -> dict:
    return {"pmid": pmid, "title": title, "abstract": abstract, "pubTypes": list(pub),
            "mesh": list(mesh), "citedByCount": cites, "date": "2020-01-01",
            "journal": "J", "journalAbbrev": "J", "doi": None}


def subject_gate() -> None:
    print("subject gate:")
    # only the unhyphenated spelling, exactly as the live planner wrote it
    queries = ['("heparin induced thrombocytopenia") AND (bivalirudin OR argatroban) '
               'AND SRC:MED']
    papers = [cand("1", "Unfractionated heparin versus LMWH for avoiding heparin-induced "
                        "thrombocytopenia"),
              cand("2", "Fibrates for secondary prevention of cardiovascular disease")]
    ranked = {r["pmid"]: r for r in pc.rank_all(papers, PROFILE, queries, DOMAIN)}
    ok(ranked["1"]["on_subject"], "'heparin-induced' in the paper matches "
       "'heparin induced' in the query")
    ok(not ranked["2"]["on_subject"], "an unrelated review stays off-subject")
    # Fixture from the live HIT run of 2026-10-16 (its evidence file was later
    # overwritten): the planner's subject facet and a paper it marked off-subject.
    live_query = ['("heparin induced thrombocytopenia" OR HIT) AND (acute OR active OR '
                  'current) AND (anticoagulation OR anticoagulant) AND SRC:MED']
    title = ("Unfractionated heparin versus low molecular weight heparins for avoiding "
             "heparin-induced thrombocytopenia in postoperative patients")
    old_gate = "heparin induced thrombocytopenia" in title.lower()   # the old substring test
    now = pc.rank_all([cand("28431186", title)], PROFILE, live_query, DOMAIN)[0]["on_subject"]
    ok(not old_gate and now, "28431186 (off-subject in the live HIT run) is on-subject now")


def r(pmid: str, on: bool, guideline: bool = False, cardiac: bool = False,
      titled: bool = True) -> dict:
    return {"pmid": pmid, "on_subject": on,
            "pubTypes": ["Practice Guideline"] if guideline else ["Journal Article"],
            "mesh": ["cardiopulmonary bypass"] if cardiac else ["wounds and injuries"],
            "score_breakdown": {"title_relevance": 40 if titled else 0}}


def selection() -> None:
    print("selection floor:")
    ranked = [r("a", True), r("b", True), r("c", True)] + [r(f"o{i}", False) for i in range(30)]
    sel = pc.select_papers(ranked, 20, DOMAIN)
    ok([s["pmid"] for s in sel] == ["a", "b", "c"], "3 on-subject + 30 off-subject: "
       "no padding, 3 selected")
    ranked = ([r("a", True)] + [r(f"g{i}", False, guideline=True, cardiac=True)
                                for i in range(5)]
              + [r("t", False, guideline=True, cardiac=False)])
    sel = pc.select_papers(ranked, 20, DOMAIN)
    ok([s["pmid"] for s in sel] == ["a", "g0", "g1", "g2"]
       and all(s.get("context_guideline") for s in sel[1:]),
       "cardiac guidelines as context: capped at 3, marked; non-cardiac guideline out")
    sel = pc.select_papers([r("a", True), r("scad", False, True, True, titled=False)],
                           20, DOMAIN)
    ok([s["pmid"] for s in sel] == ["a"],
       "cardiac guideline whose title names no query concept: not admitted")
    ranked = [r(f"on{i}", True) for i in range(25)] + [r("g", False, True, True)]
    sel = pc.select_papers(ranked, 20, DOMAIN)
    ok(len(sel) == 20 and sel[-1]["pmid"] == "g" and sum(s["on_subject"] for s in sel) == 19,
       "full on-subject set: the guideline takes the last slot, total stays 20")
    try:
        pc.select_papers([r("o1", False), r("g", False, True, True)], 20, DOMAIN)
        ok(False, "zero on-subject papers raises")
    except pc.PraxisError as e:
        ok("keine Paper zum Thema" in str(e),
           "zero on-subject (even with a context guideline): no dossier, PraxisError")


def thin_and_payload() -> None:
    print("thin-evidence note and payload:")
    sel = [{"pmid": "1", "title": "T", "abstract": "abs", "on_subject": True, "stufe": 2,
            "pubTypes": [], "journal": "J", "date": "2020"},
           {"pmid": "2", "title": "G", "abstract": "guide", "on_subject": False,
            "context_guideline": True, "stufe": 2, "pubTypes": ["Practice Guideline"],
            "journal": "J", "date": "2021"}]
    q = {"title": "Test", "frage": "F", "kontext": ""}
    user = pc.build_user(q, sel)
    ok("HINWEIS: Nur 1 der gelieferten Paper" in user, "synthesis is told the evidence is thin")
    ok('"bezug"' in user and "Kontext-Leitlinie" in user, "context guideline marked for the model")
    d = pc.finalize("## Kurzantwort\n\nText (PMID 1).", ["x"], sel, q)
    ok("> Hinweis: Nur 1 der gefundenen Paper" in d, "dossier carries the code-set thin note")
    ok(all(p for p, _ in vd.check(d)), "  ... and still passes verify_dossier")
    rich = [dict(sel[0], pmid=str(i)) for i in range(6)]
    ok("Hinweis: Nur" not in pc.finalize("x", ["x"], rich, q), "no note with 6 on-subject papers")
    rec = pc.evidence_record(q, ["x"], sel, "raw")
    ok(rec["papers"][1]["context_guideline"] is True and "bezug" in rec["papers"][1],
       "evidence.json records the marker exactly as the model saw it")


def main() -> int:
    abbreviations()
    query_cleanup()
    subject_gate()
    selection()
    thin_and_payload()
    bad = RESULTS.count(False)
    print(f"\n{len(RESULTS) - bad}/{len(RESULTS)} passed.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
