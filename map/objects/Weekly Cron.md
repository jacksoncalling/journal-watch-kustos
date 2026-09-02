---
type: Instrument
status: pending
kind: github action
hub: orchestration
---
# Weekly Cron

The automation instrument. A GitHub Action (weekly.yml) runs the orchestrator Friday 04:00 UTC, plus workflow_dispatch with a dry_run input. It auto-detects live vs dry by whether the Telegram secrets exist, so it copies unchanged into the private repo. Built, but by HANDOFF's own account not yet exercised on GitHub, hence pending, not live.

enables [[Weekly Orchestrator]] . held-by [[The Maintainer]] . depends-on [[Run Ledgers]]

- **Hits:** [[Weekly Orchestrator]] (it is the trigger). Whether the brief ever sends without a human. Its first real test is a workflow_dispatch dry-run on GitHub.
- **Does not hit:** [[Praxis-Check]], which has its own dispatch-only workflow and no schedule. The weekly cron does not drive the on-demand path.

Source: ..github/workflows/weekly.yml; HANDOFF.md stage table ('not yet run on GitHub').
