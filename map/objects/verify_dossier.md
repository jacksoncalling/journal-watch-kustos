---
type: Capability
status: live
kind: checker
hub: verification
---
# verify_dossier

The guardrail checker. Runs the seven safety checks against a produced dossier (provenance present, no dose directives, citations resolve, footer intact) and reports pass/fail. Used to confirm the web output was clean end to end. This is the offline enforcement receipt, the piece the contest field rewarded.

checks [[The Guardrails]] . depends-on [[Praxis-Check]] output

- **Hits:** trust that [[The Guardrails]] actually held on real output, not just in intent. A failing check is a loud stop.
- **Does not hit:** retrieval quality. It verifies safety and provenance, not whether the dossier found the best papers. A safe dossier can still be thin.

Source: scripts/verify_dossier.py; HANDOFF.md ('all 7 guardrails green').
