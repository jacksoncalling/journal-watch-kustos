---
type: Ghost
status: ghost
kind: unbuilt feature
hub: orchestration
---
# Per-User Quota

No per-user identity, of which the missing quota is only one symptom. The three physicians share one login and one password, so the system cannot tell them apart at all: the dossier cap is global (max_dossiers_per_day in usage.json), chat history is per-browser not per-person, and the [[Profile]] is shared. Identity is the missing primitive; quota, per-user history, and [[Real Instantiation]] all wait on it.

would-extend [[Run Ledgers]] . needed-by [[Web Seam]] . blocks [[Real Instantiation]]

- **Hits:** the cost cap's fairness, per-user history, and any per-physician profile. One global counter and one shared login mean the app treats three people as one.
- **Does not hit:** the guardrails. The daily cap already protects spend globally, and the no-patient-data notice is shown to every user regardless of identity.

Source: HANDOFF.md 'Remaining work' (per-user quota); scripts/praxis_check.py (global cap); web/index.html:295 (browser-local history); conversation with the maintainer 2026-09-02 (one shared password).
