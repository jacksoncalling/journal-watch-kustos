---
type: Capability
status: live
kind: orchestrator
hub: orchestration
---
# Weekly Orchestrator

The weekly spine. Chains the five stages as subprocesses (not imports), so if one stage exits nonzero the next never runs, failure isolation by design. It owns the one piece of real logic beyond chaining: it advances seen.json only after a confirmed send. --dry-run runs fetch..synthesize and skips send and the ledger. Verified green live 2026-08-23.

held-by [[The Maintainer]] . depends-on [[Fetch]] . depends-on [[Enrich]] . depends-on [[Rank]] . depends-on [[Synthesize]] . depends-on [[Send]] . writes [[Run Ledgers]] . enabled-by [[Weekly Cron]]

- **Hits:** [[Run Ledgers]] (it is the only writer of seen.json's cross-week dedup). The whole weekly artifact. A stage's exit code, which it treats as a hard gate.
- **Does not hit:** the [[Praxis-Check]]. They share the five transforms but compose them differently (subprocess vs import); changing the orchestrator does not touch the on-demand path.

Source: scripts/run_weekly.py:18-88.
