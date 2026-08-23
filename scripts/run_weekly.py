#!/usr/bin/env python3
"""scripts/run_weekly.py: the weekly orchestrator.

Chains the five stages fetch -> enrich -> rank -> synthesize -> send, failing
loudly (nonzero exit) the moment any stage errors, so the GitHub Action reports
red instead of sending or committing a half-built brief.

Its one piece of real logic beyond chaining is the seen.json ledger: it is
written ONLY after Telegram confirms delivery (send exit 0). Nothing else in the
pipeline writes it, so the cross-week dedup guarantee lives here. Writing it
advances last_run_date to today (next run's window starts here) and adds the
delivered papers' dedupe keys so the same paper never appears in a second brief.

  python scripts/run_weekly.py            # full run: 5 stages, then the ledger
  python scripts/run_weekly.py --dry-run  # fetch..synthesize, no send, no ledger

Design notes:
- Stages run as subprocesses (same interpreter), not imports: each stage is a
  standalone `SystemExit(main())` script with its own file I/O contract, and
  subprocess isolation is exactly the "one stage fails, the next never runs"
  behaviour the Action needs. Running the script by path also puts scripts/ on
  sys.path[0], so synthesize.py's `import providers` resolves.
- git commit/push is NOT done here. That is the Action's job (build-plan 5.5);
  keeping it out means a local run has no git side effects.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SELECTED = ROOT / "02_rank" / "output" / "selected.json"
SEEN = ROOT / "01_fetch" / "output" / "seen.json"

# The pipeline, in order. send is handled separately: it gates the ledger.
PRE_SEND = [
    ("fetch",      "fetch_europepmc.py"),
    ("enrich",     "enrich.py"),
    ("rank",       "rank.py"),
    ("synthesize", "synthesize.py"),
]


def run_stage(label: str, script: str) -> int:
    print(f"\n=== {label} ===", flush=True)
    proc = subprocess.run([sys.executable, str(SCRIPTS / script)], cwd=ROOT)
    return proc.returncode


def dedupe_key(cand: dict) -> str:
    """The key fetch_europepmc.dedupe_key uses to skip already-seen papers.
    Kept in sync by hand (both are one line); fetch is the source of truth. The
    fields (doi/pmid/id) pass through fetch -> rank unchanged, so a selected
    item yields the same key as the raw record fetch saw."""
    return (cand.get("doi") or cand.get("pmid") or cand.get("id") or "").lower()


def update_seen() -> None:
    """Advance the ledger after a confirmed send: move last_run_date to today
    and add the delivered papers' keys so they never appear in a second brief.
    Only the *delivered* (selected) papers are recorded; candidates that were
    fetched but not selected fall outside the next date window anyway, and if a
    boundary-day one reappears it simply gets a fair second chance."""
    seen = {"schema_version": "1.0", "last_run_date": None, "seen_ids": []}
    if SEEN.exists():
        seen = json.loads(SEEN.read_text(encoding="utf-8"))
        seen.setdefault("schema_version", "1.0")

    ids = set(seen.get("seen_ids", []))
    if SELECTED.exists():
        sel = json.loads(SELECTED.read_text(encoding="utf-8"))
        for c in sel.get("selected", []):
            k = dedupe_key(c)
            if k:
                ids.add(k)

    seen["last_run_date"] = date.today().isoformat()
    seen["seen_ids"] = sorted(ids)

    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"\nseen.json updated: last_run_date={seen['last_run_date']}, "
          f"{len(seen['seen_ids'])} id(s) in ledger.")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Journal Watch weekly orchestrator.")
    ap.add_argument("--dry-run", action="store_true",
                    help="run fetch..synthesize, then skip the Telegram send and "
                         "the seen.json write (method-repo / CI sanity run).")
    args = ap.parse_args(argv)

    for label, script in PRE_SEND:
        rc = run_stage(label, script)
        if rc != 0:
            print(f"\nFAILED at stage '{label}' (exit {rc}). "
                  f"Pipeline stopped; seen.json NOT advanced.", file=sys.stderr)
            return rc

    if args.dry_run:
        print("\n=== send (skipped: --dry-run) ===")
        print("dry run complete: brief written, nothing sent, ledger untouched.")
        return 0

    rc = run_stage("send", "send_telegram.py")
    if rc != 0:
        print(f"\nFAILED at stage 'send' (exit {rc}). Brief was NOT delivered; "
              f"seen.json NOT advanced, so these papers retry next run.",
              file=sys.stderr)
        return rc

    # Delivery confirmed. Only now is it safe to advance the ledger.
    update_seen()
    print("\nweekly run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
