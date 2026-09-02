---
type: Shared Resource
status: live
kind: run state
hub: memory
---
# Run Ledgers

The disposable state files, all gitignored: seen.json (cross-week dedup, written only after a confirmed send), candidates.json / selected.json (per-run pools), and usage.json (the daily dossier cap ledger). This is the 'no server, no database' bet: run state is just files in the repo, safe to delete.

written-by [[Weekly Orchestrator]] . read-by [[Fetch]] . read-by [[Praxis-Check]] . would-be-extended-by [[Per-User Quota]] . governed-by [[Folder is the Database]]

- **Hits:** cross-week dedup (seen.json) and the cost cap (usage.json). Deleting seen.json re-shows old papers; deleting usage.json resets the cap.
- **Does not hit:** [[Profile]] / [[Kanon]], the truth files. Ledgers are disposable views of run state; the config and memory are the durable truth. Never confuse the two.

Source: scripts/run_weekly.py:38-88; HANDOFF.md gap #1 (seen.json fixed).
