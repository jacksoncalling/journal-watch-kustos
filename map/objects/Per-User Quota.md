---
type: Ghost
status: ghost
kind: unbuilt feature
hub: orchestration
---
# Per-User Quota

Per-user fairness on the dossier cap. Today's cap is global (max_dossiers_per_day in usage.json); a per-user quota needs the web layer's user identity, which does not exist yet. Named, unwired.

would-extend [[Run Ledgers]] . needed-by [[Web Seam]] . blocked-on [[The Clinician]] identity

- **Hits:** the cost cap's fairness, if built. Currently one global counter protects cost; it just cannot tell users apart.
- **Does not hit:** the guardrails. The quota is a cost/fairness feature, not a safety contract; the daily cap already protects spend globally.

Source: HANDOFF.md 'Remaining work' (per-user quota); scripts/praxis_check.py (global cap).
