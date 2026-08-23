#!/usr/bin/env python3
"""Tests for the deterministic evidence-level mapping (02_rank).

Plain asserts, no framework needed: `python scripts/test_rank.py`.
The mapping is the one piece of ranking the synthesis step is forbidden to
override, so it gets pinned down here.
"""
from rank import evidence_level


def check(pub_types, expected, note):
    got = evidence_level(pub_types)
    status = "ok " if got == expected else "FAIL"
    print(f"  [{status}] Stufe {got} (want {expected})  {note}")
    return got == expected


def main() -> int:
    cases = [
        (["Meta-Analysis"], 1, "meta-analysis -> Stufe 1"),
        (["Journal Article", "Systematic Review"], 1, "systematic review -> Stufe 1"),
        (["Randomized Controlled Trial", "Multicenter Study"], 1, "multicenter RCT -> Stufe 1"),
        (["Randomized Controlled Trial"], 2, "single-site RCT -> Stufe 2"),
        (["Journal Article", "Observational Study"], 2, "observational -> Stufe 2"),
        (["Guideline"], 2, "guideline -> Stufe 2"),
        (["Journal Article", "Review"], 3, "narrative review is NOT Stufe 1"),
        (["Case Reports"], 3, "case report -> Stufe 3"),
        (["Letter"], 3, "letter -> Stufe 3"),
        (["Editorial"], 3, "editorial -> Stufe 3"),
        (["Journal Article"], 3, "plain article -> Stufe 3"),
        ([], 3, "empty pubTypes -> Stufe 3 (default)"),
    ]
    print("evidence_level mapping:")
    passed = sum(check(pt, exp, note) for pt, exp, note in cases)
    total = len(cases)
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
