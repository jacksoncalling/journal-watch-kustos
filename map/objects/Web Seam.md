---
type: Capability
status: live
kind: interface
hub: orchestration
---
# Web Seam

The FastAPI skin that lets the Praxis-Check start from a phone, and the live front door: it is published on Replit and three physicians use it now. GET / serves the page; POST /praxis returns {dossier, queries, count, citations}; POST /praxis/stream emits SSE stage events. The rebuilt frontend (web/index.html) adds a chat-history panel stored per-browser (localStorage) with a plain no-patient-data notice. Gated by one shared password, fails closed (503) if unset, hmac.compare_digest, question length 10..2000. The backend app.py is unchanged since the map was first drawn; the growth is all client-side.

held-by [[Replit]] . depends-on [[Praxis-Check]] . serves [[The Clinician]] . blocked-on [[Per-User Quota]]

- **Hits:** [[The Clinician]] and the two other physicians (their only entry point). Whatever build_dossier returns, rendered as-is. A password check that, misconfigured, closes the whole door.
- **Does not hit:** the guardrails' substance. The web layer renders Stufe/study-type/links as-is and must never recompute them client-side; it is a window, not a second brain.

Source: web/app.py; web/index.html:283-295 (history panel, browser-local, privacy notice); web/REPLIT_BRIEF.md.
