---
type: Gradient
status: live
hub: evaluative
---
# Presentation over Retrieval

Direction: the cheap wins were surfacing data Kustos already computes and hides (inline citations, study-type badges, progress), not new retrieval. Largely realized now: Replit's frontend rebuild (web/index.html, +1046 lines) added inspectable citations, real SSE progress, and a chat-history panel, and the app is published. So this gradient has mostly spent itself, in the predicted direction. What remains is the guardrail it always carried: Stufe/study_type/links are rendered as-is and must never be recomputed client-side.

pulls-on [[Web Seam]] . pulls-on [[The Clinician]]

- **Hits:** the surface the physicians actually use. The presentation work landed; the retrieval track (the [[Gate Layer]]) is untouched by it, as intended.
- **Does not hit:** retrieval quality. Better presentation did not and should not change what the search returns; it stopped hiding what search already found.

Source: web/index.html (rebuilt frontend: history panel, citations, SSE); HANDOFF.md 2026-08-30 (Fields of Inquiry reframe); git 85c284e..25d54cc.
