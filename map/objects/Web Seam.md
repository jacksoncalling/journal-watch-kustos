---
type: Capability
status: live
kind: interface
hub: orchestration
---
# Web Seam

The thin FastAPI skin that lets the Praxis-Check start from a phone, an OpenEvidence-style surface. GET / serves the page; POST /praxis returns {dossier, queries, count, citations}; POST /praxis/stream emits SSE stage events (searching, found, synthesis, done). Password-gated and fails closed (503) if KUSTOS_APP_PASSWORD is unset, hmac.compare_digest, question length 10..2000. This is the layer Replit built and hosts.

held-by [[Replit]] . depends-on [[Praxis-Check]] . serves [[The Clinician]] . would-need [[Per-User Quota]]

- **Hits:** [[The Clinician]] (her phone entry point). Whatever build_dossier returns, rendered as-is. A password check that, misconfigured, closes the whole door (fails closed).
- **Does not hit:** the guardrails' substance. The web layer renders Stufe/study-type/links as-is and must never recompute them client-side; it is a window, not a second brain.

Source: web/app.py; HANDOFF.md 2026-08-30 (WP-A/WP-B); web/REPLIT_BRIEF.md.
