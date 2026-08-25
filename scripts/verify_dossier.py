#!/usr/bin/env python3
"""Guardrail checker for a Praxis-Check dossier.

Run this on ANY dossier, whether written by scripts/praxis_check.py or produced
by a web UI (the Replit app), to prove the safety layer survived. The checks are
exactly the invariants the pipeline enforces in code:

  1. no em/en dashes anywhere (the no-dash rule)
  2. the fixed footer is present exactly once
  3. the structural sections exist (## Verwendete Suchanfrage, ## Quellen)
  4. no [Stufe]/[VOLLTEXT]/[NUR ABSTRACT] labels leak into the prose
     (they belong only in the code-built Quellen block)
  5. every inline (PMID ...) is backed by an entry in ## Quellen
     (no hallucinated citations)
  6. Quellen entries actually carry a Stufe label and a link (provenance present)

Exit 0 if every check passes, 1 otherwise. If a web app's output fails these, it
is not going through the pipeline. A stronger test still: run the same question
through `python scripts/praxis_check.py --dry-run` and diff the sources.

Usage:
  python scripts/verify_dossier.py <path-to-dossier.md>
  python scripts/verify_dossier.py            # newest in 05_praxis-check/output/
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "05_praxis-check" / "output"
FOOTER_OPENING = "Kein Ersatz für klinische Entscheidungen"


def newest_dossier() -> Path | None:
    files = sorted(OUTPUT.glob("*.md"))
    files = [f for f in files if f.name != "README.md"]
    return files[-1] if files else None


def check(text: str) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []

    # 1. no em/en dashes
    dash = text.count("–") + text.count("—")
    results.append((dash == 0, f"no em/en dashes (found {dash})"))

    # split prose from the code-built Quellen block
    parts = text.split("## Quellen")
    prose = parts[0]
    quellen = parts[1] if len(parts) > 1 else ""

    # 2. footer exactly once
    fc = text.count(FOOTER_OPENING)
    results.append((fc == 1, f"footer present exactly once (found {fc})"))

    # 3. structural sections
    results.append(("## Verwendete Suchanfrage" in text,
                    "has ## Verwendete Suchanfrage"))
    results.append((bool(quellen), "has ## Quellen"))

    # 4. no evidence/provenance labels loose in the prose
    leaked = re.findall(r"\[Stufe\s*\d\]|\[(?:VOLLTEXT|NUR ABSTRACT)\]", prose)
    results.append((not leaked,
                    f"no Stufe/provenance labels in prose (found {len(leaked)})"))

    # 5. every inline PMID is backed by a Quellen entry
    cited = set(re.findall(r"\d+", " ".join(re.findall(r"\(PMID\s+([\d,\s]+)\)", prose))))
    quellen_pmids = set(re.findall(r"PMID\s+(\d+)", quellen))
    missing = sorted(cited - quellen_pmids)
    results.append((not missing,
                    f"all inline PMIDs backed by a source (missing {missing or 'none'})"))

    # 6. Quellen entries carry Stufe + a link (provenance present)
    if quellen:
        has_stufe = bool(re.search(r"\[Stufe\s*\d\]", quellen))
        has_link = "http" in quellen
        results.append((has_stufe and has_link,
                        "Quellen carry Stufe labels and links"))
    return results


def main(argv: list[str]) -> int:
    if argv:
        path = Path(argv[0])
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
    else:
        path = newest_dossier()
        if not path:
            print(f"no dossiers in {OUTPUT}", file=sys.stderr)
            return 1

    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    print(f"checking {path.name}\n")
    results = check(text)
    ok = True
    for passed, label in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
        ok = ok and passed
    print("\n" + ("ALL GUARDRAILS HELD." if ok else "GUARDRAIL FAILURE (see FAIL lines)."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
