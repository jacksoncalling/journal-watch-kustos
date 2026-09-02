---
type: Capability
status: live
kind: orchestrator
hub: orchestration
---
# Praxis-Check

The on-demand branch (slice 1.5). Reuses the five weekly transforms by import (not subprocess), then adds the deterministic gate layer and an all-time search, to answer one clinical-literature question with a deep dossier. build_dossier(question) is the single shared callable both the CLI and the web layer call, so the guardrails live in exactly one place. Refactored into a dossier_stages() generator both paths drain.

held-by [[The Maintainer]] . depends-on [[Fetch]] . depends-on [[Enrich]] . depends-on [[Rank]] . depends-on [[Synthesize]] . depends-on [[Gate Layer]] . depends-on [[Query Planner]] . bound-by [[Dossier-Vertrag]] . reads [[Run Ledgers]]

- **Hits:** [[Web Seam]] (it sits directly on build_dossier). [[Run Ledgers]] usage.json (the daily cost cap lives here, raising DailyLimitError over the cap). The dossier a clinician reads.
- **Does not hit:** the [[Weekly Orchestrator]]'s seen.json. The Praxis-Check keeps no cross-run dedup; every question searches all-time from scratch.

Source: scripts/praxis_check.py:10, :38-42, build_dossier / dossier_stages.
