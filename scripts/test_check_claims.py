#!/usr/bin/env python3
"""Seeded-error tests for check_claims.py (and the evidence record it reads).

Plain asserts, no framework: `python scripts/test_check_claims.py`.

Each case plants one known error and checks the checker catches it, AND that
the structural checker (verify_dossier.py) does not: that gap is why
check_claims.py exists. The last block mutates a real saved dossier, so the
checks are proven on real model prose, not only on fixtures written to pass.
Offline, except that the real-dossier block needs the rebuilt
`*.evidence.json` files in 05_praxis-check/output/ (skipped if absent).
"""
from __future__ import annotations

import json
from pathlib import Path

import check_claims as cc
import praxis_check as pc
import verify_dossier as vd

OUTPUT = Path(__file__).resolve().parent.parent / "05_praxis-check" / "output"
RESULTS: list[bool] = []


def ok(cond: bool, note: str) -> None:
    print(f"  [{'ok ' if cond else 'FAIL'}] {note}")
    RESULTS.append(bool(cond))


def kinds(findings, level):
    return [f.kind for f in findings if f.level == level]


def ev(*papers):
    return {"papers": [{"pmid": p, "evidence_basis": t, "provenance": prov}
                       for p, t, prov in papers]}


def dossier(brief: str, detail: str) -> str:
    """A dossier with the code-built tail, so verify_dossier sees a valid file."""
    return (f"# Praxis-Check: Test\n\n## Kurzantwort\n\n{brief}\n\n"
            f"## Evidenzlage\n\n{detail}\n\n"
            "## Verwendete Suchanfrage\n\n- `x`\n\n## Quellen\n\n"
            "1. A\n   J, 2020 · PMID 11111111\n   [Stufe 1] [VOLLTEXT] https://x\n\n"
            "2. B\n   J, 2020 · PMID 22222222\n   [Stufe 2] [NUR ABSTRACT] https://y\n\n"
            "Kein Ersatz für klinische Entscheidungen oder Dosierungsangaben.\n")


def structurally_clean(text: str) -> bool:
    return all(passed for passed, _ in vd.check(text))


CHOOSE = ("Procedural success was achieved in 46 of 49 patients (94%). "
          "Major bleeding occurred in 41 patients (84%). "
          "Baseline characteristics were typical for cardiac surgery. "
          "Of all enrolled, 43 patients had acute HIT at the time of surgery.")
SIRS = ("We randomly assigned 7507 patients to methylprednisolone (250 mg at "
        "induction and 250 mg at bypass) or placebo. Mortality at 30 days was "
        "4.6% vs 4.9%. Myocardial injury was more frequent with steroids.")
EV = ev(("11111111", CHOOSE, "[VOLLTEXT]"), ("22222222", SIRS, "[NUR ABSTRACT]"))
GOOD_DETAIL = ("Der Eingriff gelang bei 46 von 49 Patienten (94 %) (PMID 11111111). "
               "In SIRS (7507 Patienten) lag die 30-Tage-Mortalität bei 4,6 % vs. "
               "4,9 % (PMID 22222222).")
GOOD_BRIEF = ("Die Studienlage zeigt Erfolg bei 46 von 49 Patienten (PMID 11111111). "
              "Die Steroiddaten stammen nur aus einem Abstract (PMID 22222222).")


def synthetic() -> None:
    print("synthetic cases:")
    f = cc.check(dossier(GOOD_BRIEF, GOOD_DETAIL), EV)
    got = kinds(f, "FAIL") + [k for k in kinds(f, "WARN") if k != "thin"]
    ok(not got, f"clean dossier: no FAIL/WARN apart from thin fixtures (got {got})")

    bad = GOOD_DETAIL.replace("4,6 %", "5,6 %")
    d = dossier(GOOD_BRIEF, bad)
    f = cc.check(d, EV)
    ok("number" in kinds(f, "FAIL"), "changed result 4,6 -> 5,6 %: FAIL number")
    ok(structurally_clean(d), "  ... and verify_dossier passes it (the gap)")

    # The CHOOSE-ON case from the Replit HIT simulation: overall 46/49 (94 %)
    # glued to the 43-patient acute-HIT subgroup in the brief.
    brief = ("Die Studienlage zeigt 94 % Erfolg bei 43 Patienten mit akuter HIT "
             "(PMID 11111111). Steroiddaten nur aus einem Abstract (PMID 22222222).")
    d = dossier(brief, GOOD_DETAIL)
    f = cc.check(d, EV)
    ok("pctden" in kinds(f, "FAIL"), "94 % with 43 (subgroup) in brief: FAIL pctden")
    ok("brief" in kinds(f, "WARN"), "  ... and WARN brief (43 never in the detail)")
    ok(structurally_clean(d), "  ... and verify_dossier passes it (the gap)")

    d = dossier(GOOD_BRIEF, GOOD_DETAIL + " Ein Review bestätigt das (PMID 33333333).")
    f = cc.check(d, EV)
    ok("phantom" in kinds(f, "FAIL"), "PMID not in the evidence: FAIL phantom")

    brief = "Die Studienlage zeigt keinen Mortalitätsvorteil (PMID 22222222)."
    f = cc.check(dossier(brief, GOOD_DETAIL), EV)
    ok("abstract" in kinds(f, "WARN"),
       "brief rests on an abstract-only paper, never says so: WARN abstract")

    brief = "Die Studienlage zeigt 4,6 % Mortalität (PMID 22222222), nur Abstract."
    f = cc.check(dossier(brief, "Keine Zahlen hier (PMID 11111111)."), EV)
    ok("brief" in kinds(f, "WARN") and not kinds(f, "FAIL"),
       "brief number the detail never mentions: WARN brief, not FAIL")

    f = cc.check(dossier(GOOD_BRIEF, GOOD_DETAIL + " Die Rate lag bei 12 %."), EV)
    ok("number" in kinds(f, "FAIL"),
       "uncited 12 % right after a cited sentence: checked against it, FAIL")


def formats() -> None:
    print("number formats and noise:")
    src = ev(("11111111", "In 4,494 patients, 0.5 mg/kg; rate 93.9%; 46/49 "
              "succeeded; dose 1 mg/kg.", "[VOLLTEXT]"))
    cases = [
        ("4.494 Patienten", "German thousands 4.494 = 4,494"),
        ("0,5 mg/kg", "German decimal 0,5 = 0.5"),
        ("93,9 %", "93,9 % = 93.9%"),
        ("94 %", "rounded 94 % from 93.9% (and 46/49)"),
        ("1 mg/kg", "small number with a unit is checked and found"),
    ]
    for claim, note in cases:
        f = cc.check(dossier("x", f"Befund {claim} (PMID 11111111)."), src)
        ok(not kinds(f, "FAIL"), note)
    src2 = ev(("11111111", "Patients were randomised.", "[VOLLTEXT]"))
    noise = ("IL-6 und COVID-19 in DECS-II, 2015 publiziert, in 3 Studien "
             "(PMID 11111111).")
    f = cc.check(dossier("x", noise), src2)
    ok(not kinds(f, "FAIL"), "IL-6, COVID-19, DECS-II, a year, '3 Studien' are not checked")
    f = cc.check(dossier("x", "Befund 5 mg/kg (PMID 11111111)."), src2)
    ok("number" in kinds(f, "FAIL"), "but '5 mg/kg' absent from source: FAIL")


def review_round_1() -> None:
    """Every reproduction from the first cold review (2026-10-15). Each failed
    or passed wrongly on the first version of check_claims.py."""
    print("cold review round 1 regressions:")
    choose = ev(("11111111", "Procedural success was achieved in 46 of 49 patients "
                 "(94%). Of these, 43 patients had acute HIT.", "[VOLLTEXT]"))
    bad = "Erfolg bei 94 % von 43 Patienten (PMID 11111111)."
    f = cc.check(dossier(bad + " Nur Abstract.", bad), choose)
    ok(kinds(f, "FAIL").count("pctden") == 2,
       "CHOOSE-ON error in brief AND detail, 43 adjacent in source: FAIL pctden x2")
    f = cc.check(dossier("Bei 43 Patienten lag der Erfolg bei 94 % (PMID 11111111).",
                         "x"), choose)
    ok("pctden" in kinds(f, "FAIL"), "count before the percent: FAIL pctden")
    f = cc.check(dossier("x", "Erfolg bei 46 von 49 Patienten (94 %) (PMID 11111111)."),
                 choose)
    ok(not kinds(f, "FAIL"), "correct 46 von 49 (94 %): no FAIL")

    two = ev(("11111111", "Mortality was 4.6%.", "[VOLLTEXT]"),
             ("22222222", "Mortality was 3.1%.", "[VOLLTEXT]"))
    f = cc.check(dossier("Mortalität 4,6 % bzw. 3,1 % (PMID 11111111, 22222222), "
                         "Abstract.", "Erst 4,6 % (PMID 11111111), dann 3,1 % "
                         "(PMID 22222222)."), two)
    ok(not kinds(f, "FAIL") and "brief" not in kinds(f, "WARN"),
       "multi-PMID brief with both values right: no FAIL, no brief WARN")

    dose = ev(("33333333", "Tranexamic acid 1 g bolus, then 10 mg/kg/h. "
               "Methylprednisolone 1 mg/kg. Propofol 6 microg/mL. "
               "Dexamethasone 1.5 mg kg-1 h-1.", "[VOLLTEXT]"))
    for claim, want, note in [
        ("1 mg/kg/h Methylprednisolon", True, "1 mg/kg -> 1 mg/kg/h: FAIL"),
        ("10 mg Tranexamsäure", True, "10 mg/kg/h -> 10 mg: FAIL"),
        ("10 g Tranexamsäure", True, "10 g (only 1 g in source): FAIL"),
        ("1 g Tranexamsäure", False, "1 g: no FAIL"),
        ("10 mg/kg/h Tranexamsäure", False, "10 mg/kg/h: no FAIL"),
        ("6 µg/mL Propofol", False, "6 µg/mL vs 'microg/mL': no FAIL"),
        ("1,5 mg/kg/h Dexamethason", False, "1,5 mg/kg/h vs 'mg kg-1 h-1': no FAIL"),
    ]:
        f = cc.check(dossier("x", f"Gabe von {claim} (PMID 33333333)."), dose)
        ok(("number" in kinds(f, "FAIL")) == want, note)
    f = cc.check(dossier("x", "Erfolg bei 46 % (PMID 11111111)."),
                 ev(("11111111", "46/49 (94%) succeeded.", "[VOLLTEXT]")))
    ok("number" in kinds(f, "FAIL"), "'46 %' from '46/49 (94%)': FAIL")

    sirs = ev(("22222222", "We randomly assigned 7507 patients. Mortality at 30 "
               "days was 4.6% vs 4.9%. RR 0.70 (95% CI 0.59-0.82).", "[VOLLTEXT]"))
    for claim, want, note in [
        ("In 2.000 Patienten", True, "sample size 2.000 (not a year): FAIL"),
        ("In 1950 Patienten", True, "1950 with a count noun is not a year: FAIL"),
        ("Rate 7 Prozent", True, "'7 Prozent' is checked as a percent: FAIL"),
        ("Rate 30 Prozent", True, "'30 Prozent' not backed by '30 days': FAIL"),
        ("RR 0,70, 95 % CI 0,59 bis 0,82", False, "RR 0,70 before '95 % CI': no FAIL"),
        ("Mortalität 4,6 % vs. Placebo 4,9 %", False, "'vs.' does not split: no FAIL"),
    ]:
        f = cc.check(dossier("x", f"{claim} (PMID 22222222)."), sirs)
        ok(("number" in kinds(f, "FAIL")) == want, note)
    f = cc.check(dossier("x", "Mortalität 5,6 % vs. Placebo 4,9 % (PMID 22222222)."), sirs)
    ok("number" in kinds(f, "FAIL"), "wrong 5,6 % before 'vs.': FAIL (was WARN)")
    f = cc.check(dossier("x", "Die Mortalität lag bei 9,9 %. Das zeigte SIRS "
                         "(PMID 22222222)."), sirs)
    ok("number" in kinds(f, "FAIL"), "number one sentence before its citation: FAIL")
    f = cc.check(dossier("x", "Die Rate lag bei 12 %. Mehr ist nicht bekannt."), sirs)
    ok("uncited" in kinds(f, "WARN"), "number with no citation nearby: WARN uncited")

    for grp in ["(vgl. PMID 99999999)", "[PMID 99999999]", "(Studie, PMID 99999999)",
                "(PMID: 99999999)", "(PMIDs 22222222, 99999999)"]:
        f = cc.check(dossier("x", f"Befund {grp}."), sirs)
        ok("phantom" in kinds(f, "FAIL"), f"phantom in {grp}: FAIL")

    d = dossier("Mortalität 4,6 % (PMID 22222222).", "y")
    f = cc.check(d.replace("## Kurzantwort", "## Kurzantwort:"),
                 {"papers": [{"pmid": "22222222", "evidence_basis": "Mortality 4.6%.",
                              "provenance": "[NUR ABSTRACT]"}]})
    ok("abstract" in kinds(f, "WARN"), "'## Kurzantwort:' still runs the brief checks")
    f = cc.check(dossier("x", "y").replace("## Kurzantwort", "## Zusammenfassung"), sirs)
    ok("nobrief" in kinds(f, "WARN"), "new-format dossier without Kurzantwort: WARN")

    f = cc.check(dossier("x", "Odds Ratio 1,13 (95 %-KI 1,02 bis 1,24) (PMID 44444444)."),
                 ev(("44444444", "OR 1.125 (95% CI 1.020 to 1.240).", "[VOLLTEXT]")))
    ok(not kinds(f, "FAIL"), "OR 1,13 vs 1.125 (float rounding): no FAIL")

    f = cc.check(dossier("x", "Befund (PMID 55555555)."),
                 ev(("55555555", "The content is available as a PDF (28.4 MB).",
                     "[VOLLTEXT]")))
    ok("thin" in kinds(f, "WARN"), "[VOLLTEXT] with a PDF stub as text: WARN thin")


def review_round_2() -> None:
    """Reproductions from the second cold review (2026-10-15)."""
    print("cold review round 2 regressions:")
    src = ev(("11111111", "We enrolled 1,850 patients in 2 groups. The odds ratio "
              "was 1.5.", "[VOLLTEXT]"))
    for claim, note in [("2.000 Patienten", "2.000 Patienten (source 1,850): FAIL"),
                        ("1.500 Patienten", "1.500 Patienten: FAIL")]:
        f = cc.check(dossier("x", f"Die Studie schloss {claim} ein (PMID 11111111)."), src)
        ok("number" in kinds(f, "FAIL"), note)
    f = cc.check(dossier("x", "Die Studie schloss 1.850 Patienten ein (PMID 11111111)."), src)
    ok(not kinds(f, "FAIL"), "1.850 Patienten (correct): no FAIL")

    for source, note in [
        ("achieved in 46 of the 49 patients (94%). Of all enrolled, 43 patients had "
         "acute HIT.", "'46 of the 49' in source"),
        ("Success: 46 (94%) of 49 patients. 43 patients had acute HIT.",
         "'46 (94%) of 49' in source"),
    ]:
        f = cc.check(dossier("x", "Der Erfolg lag bei 94 % von 43 Patienten "
                             "(PMID 11111111)."), ev(("11111111", source, "[VOLLTEXT]")))
        ok("pctden" in kinds(f, "FAIL"), f"CHOOSE-ON with {note}: FAIL pctden")
    choose = ev(("11111111", "Procedural success was achieved in 46 of 49 patients "
                 "(94%). Of these, 43 patients had acute HIT.", "[VOLLTEXT]"))
    f = cc.check(dossier("x", "Bei den 43 Patienten mit akuter HIT zum Zeitpunkt der "
                         "Operation lag der Erfolg bei 94 % (PMID 11111111)."), choose)
    ok("pctden" in kinds(f, "FAIL"), "count far (11 words) from the percent: FAIL pctden")

    mort = ev(("22222222", "We randomly assigned 7507 patients. Death at 30 days "
               "occurred in 173 of 3755 patients (4.6%). Delirium occurred in 12 of "
               "100 patients over 70 years (12%).", "[VOLLTEXT]"))
    for claim, note in [
        ("Die 30-Tage-Mortalität lag bei 4,6 %", "30-Tage is not a cohort count"),
        ("Bei Patienten über 70 Jahren trat ein Delir bei 12 % auf", "age 70 is not a count"),
        ("In SIRS (7507 Patienten) lag die Mortalität bei 4,6 %", "trial N in brackets"),
        ("Bei 7507 Patienten lag die Mortalität bei 4,6 %", "trial N larger than 3755"),
    ]:
        f = cc.check(dossier("x", f"{claim} (PMID 22222222)."), mort)
        ok(not kinds(f, "FAIL"), f"{note}: no FAIL")

    for claim, source, note in [
        ("p = 0,003", "(P = .003)", "p = 0,003 vs 'P = .003'"),
        ("65 mmHg", "MAP above 65 mm Hg", "65 mmHg vs 'mm Hg'"),
        ("4 mg/kg/h", "4 mg/kg/hr", "mg/kg/h vs mg/kg/hr"),
        ("4 mg/kg/h", "4 mg.kg-1.h-1", "mg/kg/h vs mg.kg-1.h-1"),
        ("4 mg/kg/h", "4 mg/kg per hour", "mg/kg/h vs 'mg/kg per hour'"),
        ("1 mg/kgKG", "1 mg/kg", "mg/kgKG vs mg/kg"),
        ("1 mg pro kg", "1 mg/kg", "'mg pro kg' vs mg/kg"),
        ("300 IE/kg", "300 U/kg", "IE/kg vs U/kg"),
        ("5000 IE", "5000 units", "IE vs units"),
        ("41.021 Patienten", "In 41 021 patients", "thin-space thousands"),
    ]:
        f = cc.check(dossier("x", f"Wert {claim} (PMID 33333333)."),
                     ev(("33333333", source, "[VOLLTEXT]")))
        ok(not kinds(f, "FAIL"), f"{note}: no FAIL")
    for source, note in [("4 milligrams per kilogram per hour", "spelled-out units"),
                         ("4 μg·kg⁻¹·h⁻¹", "superscript exponents")]:
        claim = "4 µg/kg/h" if "μg" in source else "4 mg/kg/h"
        f = cc.check(dossier("x", f"Wert {claim} (PMID 33333333)."),
                     ev(("33333333", source, "[VOLLTEXT]")))
        ok(not kinds(f, "FAIL"), f"{note}: no FAIL")
    f = cc.check(dossier("x", "Wert 4 mg/kg/h (PMID 33333333)."),
                 ev(("33333333", "4 mg/kg/minute", "[VOLLTEXT]")))
    ok("number" in kinds(f, "FAIL"), "mg/kg/h vs a per-minute source: FAIL")
    f = cc.check(dossier("x", "Wert 40 mg/kg/h (PMID 33333333)."),
                 ev(("33333333", "Dosis 40 Milligramm je Kilo", "[VOLLTEXT]")))
    ok(not kinds(f, "FAIL") and "unit" in kinds(f, "WARN"),
       "unknown unit spelling with the value present: WARN unit, not FAIL")
    f = cc.check(dossier("x", "Wert 2 mg/kg (PMID 33333333)."),
                 ev(("33333333", "Patients were split into 2 groups.", "[VOLLTEXT]")))
    ok("number" in kinds(f, "FAIL"), "small dose 2 mg/kg vs a bare '2 groups': FAIL")

    f = cc.check(dossier("x", "Der Erfolg war hoch (99 %, PMID 11111111)."), choose)
    ok("number" in kinds(f, "FAIL"), "number inside the citation bracket is checked")
    f = cc.check(dossier("x", "Groß (n = 14590; PMID 11111111)."), choose)
    ok("phantom" not in kinds(f, "FAIL"), "'n = 14590' in a bracket is not a phantom PMID")
    f = cc.check(dossier("x", "13 % von 180 Patienten (PMID 44444444)."),
                 ev(("44444444", "25 of 200 (12.5%) had events.", "[VOLLTEXT]")))
    ok("pctden" in kinds(f, "FAIL"), "13 % (12.5 % = 25/200) tied to 180: FAIL pctden")

    two = ev(("55555555", "We randomly assigned 7507 patients.", "[VOLLTEXT]"),
             ("66666666", "Mortality was 4.6% vs 4.9% at 30 days.", "[VOLLTEXT]"))
    f = cc.check(dossier("x", "SIRS randomisierte 7507 Patienten (PMID 55555555). Die "
                         "Mortalität lag bei 4,6 % vs. 4,9 %. Eine Metaanalyse "
                         "bestätigte das (PMID 66666666)."), two)
    ok(not kinds(f, "FAIL"), "continuation sentence leaning on the previous citation: no FAIL")


def review_round_3() -> None:
    """The three HIGH findings of the third cold review (2026-10-16), fixed."""
    print("cold review round 3 regressions:")
    choose = ev(("11111111", "Procedural success was achieved in 46 of 49 patients "
                 "(94%). Of these, 43 patients had acute HIT.", "[VOLLTEXT]"))
    for claim, note in [
        ("Eine Studie mit 43 Patienten zeigte 94 % Erfolg", "'mit 43 Patienten'"),
        ("Erfolg 94 % in 43 Patienten", "'in 43 Patienten'"),
        ("94 % Erfolg (n = 43)", "'(n = 43)'"),
    ]:
        f = cc.check(dossier("x", f"{claim} (PMID 11111111)."), choose)
        ok("pctden" in kinds(f, "FAIL"), f"CHOOSE-ON in house style {note}: FAIL pctden")
    f = cc.check(dossier("x", "Eine Studie mit 49 Patienten zeigte 94 % Erfolg "
                         "(PMID 11111111)."), choose)
    ok(not kinds(f, "FAIL"), "'mit 49 Patienten ... 94 %' (correct): no FAIL")

    for claim, source, note in [
        ("30 mg/kg", "30 children received methylprednisolone 15 mg/kg.", "count 30"),
        ("40 mg/kg/h", "BIS 40-60 was targeted; 10 mg/kg.", "BIS 40"),
        ("64 mg", "64 patients received 32 mg.", "64 patients"),
    ]:
        f = cc.check(dossier("x", f"Gabe von {claim} (PMID 33333333)."),
                     ev(("33333333", source, "[VOLLTEXT]")))
        ok("number" in kinds(f, "FAIL"), f"wrong dose {claim} vs bare {note}: FAIL, not WARN")

    lancet = ev(("22222222", "RR 0·87, 95% CI 0·70-1·07, p=0·19. Mortality "
                 "4·6% vs 4·9%.", "[NUR ABSTRACT]"))
    f = cc.check(dossier("x", "RR 0,87; 95 %-KI 0,70 bis 1,07; p = 0,19; Mortalität "
                         "4,6 % vs. 4,9 % (PMID 22222222)."), lancet)
    ok(not kinds(f, "FAIL"), "Lancet middle-dot decimals, correct claim: no FAIL")
    f = cc.check(dossier("x", "Mortalität 6 % vs. 9 % (PMID 22222222)."), lancet)
    ok(kinds(f, "FAIL").count("number") == 2,
       "wrong 6 % vs 9 % against '4·6% vs 4·9%': FAIL x2")


def anchored(brief_raw: str, detail_raw: str, *papers):
    """(display dossier, evidence) for raw model prose with quote anchors, the
    way praxis_check builds them: display has plain (PMID ...), the evidence
    keeps the raw prose."""
    raw = f"## Kurzantwort\n\n{brief_raw}\n\n## Evidenzlage\n\n{detail_raw}\n"
    shown = dossier(cc.split_anchors(brief_raw)[0], cc.split_anchors(detail_raw)[0])
    evd = ev(*papers)
    evd["synthesis_raw"] = raw
    return shown, evd


def quote_anchoring() -> None:
    """Quote-anchored mode (PLAN-quote-anchoring.md, option A, 2026-10-16)."""
    print("quote anchoring:")
    raw = ('Erfolg bei 46 von 49 (PMID 11111111: "achieved in 46 of 49 patients '
           '(94%)"). Kein Vorteil (PMID 11111111: "no benefit at 30 days"; '
           'PMID 22222222: "mortality 4.6% vs 4.9%"). Alt (PMID 33333333).')
    shown, _, anc = cc.split_anchors(raw)
    ok("(PMID 11111111)" in shown and "(PMID 11111111, 22222222)" in shown
       and "(PMID 33333333)" in shown and '"' not in shown,
       "display: anchors become plain (PMID ...), plain groups untouched, no quotes left")
    ok(len(anc) == 2 and anc[0]["quotes"][0][1] == "achieved in 46 of 49 patients (94%)",
       "quote with brackets inside is read whole")
    raw_dash = 'KI 0,59 bis 0,82 (PMID 11111111: "RR 0.70, 95% CI 0.59–0.82")'
    ok("–" in cc.split_anchors(raw_dash)[2][0]["quotes"][0][1],
       "en dash inside a quote is kept verbatim (split happens before dash strip)")
    ok(cc.split_anchors('x (PMID 11111111: „deutsche Anführung“).')[2] != [],
       "German quote marks „…“ are accepted")

    choose = ("11111111", "Procedural success was achieved in 46 of 49 patients "
              "(94%). Of these, 43 patients had acute HIT.", "[VOLLTEXT]")
    good = ('Erfolg bei 46 von 49 Patienten (94 %) (PMID 11111111: "Procedural '
            'success was achieved in 46 of 49 patients (94%)").')
    d, e = anchored(good + " Nur Abstract.", good, choose)
    f, met = cc.check_with_metrics(d, e)
    got = kinds(f, "FAIL") + [k for k in kinds(f, "WARN") if k != "thin"]
    ok(not got and met["quoted_claims"] == met["cited_claims"] == 2
       and met["verbatim"] == met["quotes"] == 1 and met["numbers_in_quote"] > 0,
       f"correct anchored claim: clean, metrics 2/2 quoted, 1/1 verbatim (got {got})")
    ok(structurally_clean(d), "  ... and the shown dossier passes verify_dossier")

    for quote, note in [
        ("Success was reached in 46 of the 49 patients", "paraphrased quote"),
        ("Erfolg wurde bei 46 von 49 Patienten erreicht", "translated quote"),
        ("Mortality was 4.6% in the steroid group", "quote from another paper"),
    ]:
        d, e = anchored("x", f'Erfolg 46 von 49 (PMID 11111111: "{quote}").', choose,
                        ("22222222", "Mortality was 4.6% in the steroid group.",
                         "[VOLLTEXT]"))
        ok("quote" in kinds(cc.check(d, e), "FAIL"), f"{note}: FAIL quote")

    d, e = anchored("x", 'Erfolg 94 % von 43 Patienten (PMID 11111111: "achieved in '
                    '46 of 49 patients (94%)").', choose)
    ok("number" in kinds(cc.check(d, e), "FAIL"),
       "CHOOSE-ON anchored: 43 is not in its quote: FAIL number")
    d, e = anchored("x", 'Erfolg 94 % von 43 Patienten (PMID 11111111: "achieved in '
                    '46 of 49 patients (94%)... 43 patients had acute HIT").', choose)
    ok("pctden" in kinds(cc.check(d, e), "FAIL"),
       "CHOOSE-ON with both numbers quoted: FAIL pctden on the quote")

    # the pool-mode known failures that anchoring closes
    d, e = anchored("x", 'Die Übelkeit sank um 40 % (PMID 77777777: "Ondansetron '
                    'reduced nausea compared with placebo").',
                    ("77777777", "Ondansetron reduced nausea compared with placebo. "
                     "Ondansetron ranked 2/5 among the drugs.", "[VOLLTEXT]"))
    ok("number" in kinds(cc.check(d, e), "FAIL"), "M4 anchored: 40 % not in quote: FAIL")
    d, e = anchored("x", '30 % von 241 Patienten (PMID 44444445: "Events occurred in '
                    '36/120 (30%) patients").',
                    ("44444445", "Events occurred in 36/120 (30%) patients; 241 were "
                     "randomised.", "[VOLLTEXT]"))
    ok("number" in kinds(cc.check(d, e), "FAIL"),
       "total-N limit anchored: 241 not in quote: FAIL")
    d, e = anchored("x", 'Die Mortalität lag bei 12 % (PMID 66666666: "Mortality did '
                    'not differ between groups").',
                    ("66666666", "Mortality did not differ between groups. Delirium "
                     "occurred in 12% of patients.", "[VOLLTEXT]"))
    ok("number" in kinds(cc.check(d, e), "FAIL"),
       "L7 class anchored: 12 % elsewhere in the paper, not in quote: FAIL")

    src = ("22222222", "<h4>Findings</h4>Mortality 4·6% vs 4·9% (RR 0·94, 95% CI "
           "0·80–1·10).", "[NUR ABSTRACT]")
    d, e = anchored("x", 'Mortalität 4,6 % vs. 4,9 % (PMID 22222222: "Mortality 4.6% '
                    'vs 4.9% (RR 0.94, 95% CI 0.80-1.10)").', src)
    ok(not kinds(cc.check(d, e), "FAIL"),
       "quote matches despite <h4>, middle dots and dash variants")
    d, e = anchored("x", 'Mortalität 4,6 % (PMID 22222222: "Mortality 4·6% ... '
                    'RR 0·94").', src)
    ok(not kinds(cc.check(d, e), "FAIL"), "ellipsis parts in order: no FAIL")
    d, e = anchored("x", 'Mortalität 4,6 % (PMID 22222222: "RR 0·94 ... '
                    'Mortality 4·6%").', src)
    ok("quote" in kinds(cc.check(d, e), "FAIL"), "ellipsis parts out of order: FAIL quote")

    two = (("55555555", "We randomly assigned 7507 patients to steroids or placebo.",
            "[VOLLTEXT]"),
           ("66666666", "Mortality was 4.6% vs 4.9% at 30 days in the trial.",
            "[VOLLTEXT]"))
    d, e = anchored("x", '7507 Patienten, Mortalität 4,6 % (PMID 55555555: "We '
                    'randomly assigned 7507 patients"; PMID 66666666: "Mortality was '
                    '4.6% vs 4.9% at 30 days").', *two)
    ok(not kinds(cc.check(d, e), "FAIL"), "multi-PMID anchor: each quote in its paper")
    d, e = anchored("x", '7507 Patienten, Mortalität 4,6 % (PMID 55555555: "Mortality '
                    'was 4.6% vs 4.9% at 30 days"; PMID 66666666: "We randomly '
                    'assigned 7507 patients").', *two)
    ok(kinds(cc.check(d, e), "FAIL").count("quote") == 2,
       "multi-PMID anchor with quotes swapped between papers: FAIL quote x2")

    d, e = anchored("x", good + ' Die Rate lag bei 12 % (PMID 11111111).', choose)
    f = cc.check(d, e)
    ok("unanchored" in kinds(f, "WARN") and "number" in kinds(f, "FAIL"),
       "numeric claim without a quote: WARN unanchored, still screened (FAIL)")
    d, e = anchored("x", 'Erfolg 46 von 49 (PMID 11111111: "46 of 49").', choose)
    ok("quotelen" in kinds(cc.check(d, e), "WARN"), "3-word quote: WARN quotelen")
    d, e = anchored('Erfolg bei 47 von 49 (PMID 11111111: "achieved in 46 of 49 '
                    'patients (94%)"). Abstract.', good, choose)
    ok("number" in kinds(cc.check(d, e), "FAIL"),
       "wrong number in the Kurzantwort, anchored: FAIL number")

    # live benchmark 2026-10-16: two normalizer bugs that failed real verbatim quotes
    # the quoted sentence sits BETWEEN "<" and ">", as in the live abstract;
    # the old tag stripper removed exactly that span
    ho = ("19332460", "Atrial fibrillation fell (relative risk, 0.74; P<0.01). "
          "Hyperglycemia was common (28.2%). Adults (>18 years of age) were "
          "included.", "[NUR ABSTRACT]")
    d, e = anchored("x", 'Hyperglykämie 28,2 % (PMID 19332460: "hyperglycemia was '
                    'common (28.2%)").', ho)
    ok(not kinds(cc.check(d, e), "FAIL"),
       "'P<0.01 ... >18' in the source is not an HTML tag: quote found")
    four = ("32912280", "60% of patients received heparin anticoagulation. Bleeding was "
            "common. Thus the anticoagulation strategy remain controversial.", "[VOLLTEXT]")
    d, e = anchored("x", '60 % Heparin (PMID 32912280: "60% of patients received heparin '
                    'anticoagulation....the anticoagulation strategy remain '
                    'controversial").', four)
    ok(not kinds(cc.check(d, e), "FAIL"), "four-dot ellipsis after a sentence end: found")
    d, e = anchored("x", 'Vorhofflimmern sank (PMID 19332460: "Atrial fibrillation fell '
                    '(P<0.01)").', ho)
    ok("quote" in kinds(cc.check(d, e), "FAIL"),
       "quote with a silently dropped middle part: still FAIL quote")

    trop = ("16884976", "Peak troponin I with volatile anesthetics, 1.2 (0.9-1.9) ng/dL, "
            "compared with TIVA, 2.7 (2.1-4.0) ng/dL. Stay was 10 [9-11] days.",
            "[NUR ABSTRACT]")
    d, e = anchored("x", 'Troponin 1,2 vs. 2,7 ng/dl (PMID 16884976: "volatile anesthetics, '
                    '1.2 (0.9-1.9) ng/dL, compared with TIVA, 2.7 (2.1-4.0) ng/dL").', trop)
    ok(not kinds(cc.check(d, e), "FAIL"), "value (CI) unit: '1.2 (0.9-1.9) ng/dL' read as ng/dl")
    d, e = anchored("x", 'Troponin 1,2 mg/dl (PMID 16884976: "volatile anesthetics, '
                    '1.2 (0.9-1.9) ng/dL").', trop)
    ok("number" in kinds(cc.check(d, e), "FAIL"), "  ... but 1,2 mg/dl (wrong unit): FAIL")

    sel = [{"pmid": "11111111", "abstract": choose[1], "fullTextExcerpt": None}]
    rec = pc.evidence_record({"title": "t", "frage": "f", "kontext": ""}, ["q"], sel,
                             'A (PMID 11111111: "achieved in 46 of 49 patients (94%)"). '
                             'B (PMID 11111111: "made up words here now").')
    ok([a["in_source"] for a in rec["anchors"]] == [True, False],
       "evidence_record lists anchors with in_source set by code")


def anchor_leaks() -> None:
    """Quote text must never reach the shown dossier (benchmark 2026-10-16:
    2 of 18 dossiers leaked English source text with the strict parser)."""
    print("anchor parsing, no quote leaks:")
    raw = ('Phasen (PMID 34889428: "Next, the "phase of HIT" (acute HIT, subacute HIT A/B, '
           'or remote HIT) should be established"). Weiter.')
    shown, _, anc = cc.split_anchors(raw)
    ok(shown == "Phasen (PMID 34889428). Weiter." and anc[0]["quotes"][0][1].startswith(
       'Next, the "phase of HIT"'), "quote marks inside the quote: no leak, quote kept whole")
    raw = ('Troponin (PMID 17156509: "There was a significant (P < 0.001) difference"; '
           '"reduced need for inotropic support (24/75, 32.0% vs. 31/75, 41.3%)"). Ende.')
    shown, _, anc = cc.split_anchors(raw)
    ok(shown == "Troponin (PMID 17156509). Ende." and len(anc[0]["quotes"]) == 2
       and all(p == "17156509" for p, _ in anc[0]["quotes"]),
       "second quote without repeating 'PMID x:': both quotes kept, no leak")
    shown, _, anc = cc.split_anchors('A (PMID 11111111: "q one"; PMID 22222222). B.')
    ok(shown == "A (PMID 11111111, 22222222). B." and anc[0]["quotes"] == [("11111111", "q one")],
       "mixed group: quoted and plain PMID together")
    shown, _, _ = cc.split_anchors('A (PMID 11111111: "unterminated quote runs on\nNext line.')
    ok(not cc.quote_leaks(shown) and "Next line." in shown,
       "unterminated quote: cut at line end, next line kept")
    runs = sorted(Path(__file__).resolve().parent.parent.joinpath(
        "05_praxis-check", "benchmark-runs").glob("**/*.evidence.json"))
    leaked = []
    for p in runs:
        raw = json.loads(p.read_text(encoding="utf-8")).get("synthesis_raw") or ""
        leaked += [(p.name, x) for x in cc.quote_leaks(cc.split_anchors(raw)[0])]
    ok(runs and not leaked, f"all {len(runs)} saved live raw texts: no quote reaches the "
       f"shown text (leaks: {leaked[:2]})")


KNOWN: list[tuple[bool, str]] = []


def known(fixed: bool, note: str) -> None:
    """A finding we decided NOT to fix yet (2026-10-16). It is expected to
    fail; if it starts passing, move it into a regression block."""
    print(f"  [{'NOW FIXED, promote' if fixed else 'known'}] {note}")
    KNOWN.append((fixed, note))


def known_failures() -> None:
    """Open holes from cold review round 3, kept in on purpose. The checker
    is a screen, not proof: these show where it is blind. Shared cause:
    matching is pool-based (any value anywhere in the cited text counts) and
    not tied to the words around the number."""
    print("known failures (expected to fail, not counted):")
    f = cc.check(dossier("x", "Die Übelkeit sank um 40 % (PMID 77777777)."),
                 ev(("77777777", "Ondansetron ranked 2/5 among the drugs.", "[VOLLTEXT]")))
    known("number" in kinds(f, "FAIL"),
          "M4 wrong 40 % backed by 'ranked 2/5' (ratio percentages pool too freely)")
    f = cc.check(dossier("x", "Bei 2239 Dexamethason-Patienten waren 99,7 % auswertbar "
                         "(PMID 88888888)."),
                 ev(("88888888", "Of the 4494 patients randomised, 4482 (99.7%) were "
                     "analysed.", "[VOLLTEXT]")))
    known("pctden" in kinds(f, "FAIL"),
          "M5 reversed order 'Of the N ..., a (x%)' not read as a/b")
    f = cc.check(dossier("x", "Metoprolol 50 mg/Tag (PMID 99999998)."),
                 ev(("99999998", "Metoprolol 50 mg/d was given.", "[VOLLTEXT]")))
    known(not kinds(f, "FAIL"), "M6 German per-units: '50 mg/Tag' vs '50 mg/d' false FAIL")
    two = ev(("55555555", "We randomly assigned 7507 patients.", "[VOLLTEXT]"),
             ("66666666", "Delirium occurred in 12% of patients.", "[VOLLTEXT]"))
    f = cc.check(dossier("x", "SIRS randomisierte 7507 Patienten (PMID 55555555).\n\n"
                         "Die Mortalität lag bei 12 %.\n\nEine Kohortenstudie fand "
                         "häufig Delir (PMID 66666666)."), two)
    known("number" in kinds(f, "FAIL"),
          "L7 neighbour binding crosses paragraphs: wrong 12 % backed by an unrelated "
          "paper")
    f = cc.check(dossier("x", "Kein Vorteil (PMID 55555555 und 66666666)."), two)
    known(not kinds(f, "FAIL"), "L8 '(PMID a und b)': second PMID read as a number")
    f = cc.check(dossier("x", "Unter den 70-jährigen Patienten lag die Delirrate bei "
                         "12 % (PMID 44444444)."),
                 ev(("44444444", "Delirium in 12 of 100 patients over 70 (12%).",
                     "[VOLLTEXT]")))
    known(not kinds(f, "FAIL"), "L9 age '70-jährigen' read as a cohort count")
    f = cc.check(dossier("x", "30 % von 241 Patienten (PMID 44444445)."),
                 ev(("44444445", "Events in 36/120 (30%); 241 were randomised.",
                     "[VOLLTEXT]")))
    known("pctden" in kinds(f, "FAIL"),
          "LIMIT subgroup result reported over the larger total N passes (total-N rule)")
    f = cc.check(dossier("x", "Tranexamsäure 1 g (PMID 44444446)."),
                 ev(("44444446", "Tranexamic acid 1000 mg.", "[VOLLTEXT]")))
    known(not kinds(f, "FAIL"), "LIMIT no unit conversion: '1 g' vs '1000 mg' false FAIL")


def evidence_record() -> None:
    print("evidence record (praxis_check):")
    sel = [{"pmid": "1", "title": "T", "abstract": "abs", "fullTextExcerpt": None,
            "stufe": 2, "on_subject": True, "score": 10},
           {"pmid": "2", "title": "U", "abstract": "abs2", "fullTextExcerpt": "full",
            "stufe": 1, "on_subject": False, "score": 5}]
    q = {"title": "t", "frage": "f", "kontext": ""}
    rec = pc.evidence_record(q, ["query"], sel, "raw prose")
    ok(rec["schema_version"] == 1 and rec["reconstructed"] is False, "schema + flag")
    ok([p["evidence_basis"] for p in rec["papers"]] == ["abs", "full"],
       "evidence_basis is what the model got (full text wins over abstract)")
    ok([p["provenance"] for p in rec["papers"]] == ["[NUR ABSTRACT]", "[VOLLTEXT]"],
       "provenance set in code")
    ok(rec["synthesis_raw"] == "raw prose", "raw model prose kept")
    json.dumps(rec)  # must serialize
    ok(pc.evidence_path(Path("a/2026-10-15-x.md")).name == "2026-10-15-x.evidence.json",
       "evidence file sits next to the dossier")


def real_dossier() -> None:
    md = OUTPUT / "2026-08-24-aortenklemme-kortikosteroide.md"
    js = pc.evidence_path(md)
    print(f"real dossier ({md.name}):")
    if not js.exists():
        print("  [skip] no evidence file; run scripts/rebuild_evidence.py first")
        return
    text = md.read_text(encoding="utf-8")
    evd = json.loads(js.read_text(encoding="utf-8"))
    ok(not kinds(cc.check(text, evd), "FAIL"), "baseline: no FAIL")
    for a, b, note in [("7507", "7705", "SIRS sample size 7507 -> 7705"),
                       ("4494", "4949", "DECS sample size 4494 -> 4949"),
                       ("1 mg/kg Dexamethason", "2 mg/kg Dexamethason",
                        "DECS dose 1 -> 2 mg/kg")]:
        assert a in text, a
        seeded = text.replace(a, b, 1)
        f = cc.check(seeded, evd)
        ok("number" in kinds(f, "FAIL") and structurally_clean(seeded) == structurally_clean(text),
           f"{note}: FAIL number, verify_dossier unchanged")
    # A Kurzantwort that misstates SIRS, on top of the real detailed sections.
    brief = ("## Kurzantwort\n\nDie Studienlage zeigt in SIRS mit 7000 Patienten "
             "keinen Vorteil (PMID 26460660).\n\n")
    seeded = text.replace("## Evidenzlage", brief + "## Evidenzlage", 1)
    f = cc.check(seeded, evd)
    ok("number" in kinds(f, "FAIL") and "brief" in kinds(f, "WARN"),
       "brief says 7000 where the detail says 7507: FAIL number + WARN brief")


def main() -> int:
    synthetic()
    formats()
    review_round_1()
    review_round_2()
    review_round_3()
    quote_anchoring()
    anchor_leaks()
    evidence_record()
    real_dossier()
    known_failures()
    n_bad = RESULTS.count(False)
    n_known = sum(not fixed for fixed, _ in KNOWN)
    print(f"\n{len(RESULTS) - n_bad}/{len(RESULTS)} passed; "
          f"{n_known} known failure(s) still open (see known_failures).")
    return 1 if n_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
