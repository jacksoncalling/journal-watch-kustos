---
type: Instrument
status: live
kind: policy contract
hub: contracts
---
# The Guardrails

The non-negotiable behaviour contract from build-plan section 3, enforced in code, not by the model: no dosage recommendations, no paywall circumvention, no patient data, provenance (Stufe + [VOLLTEXT]/[NUR ABSTRACT]) set in code, and no em-dashes (checked in synthesize post-processing). Because they wrap the deterministic stages, they hold regardless of what the LLM does.

binds [[Synthesize]] . binds [[Rank]] . binds [[Send]] . binds [[Enrich]] . checked-by [[verify_dossier]] . governed-by [[Regulatory Boundary]]

- **Hits:** [[Synthesize]] (the only stage that could break them) and the reader's trust. [[verify_dossier]] exists to prove they held on real output.
- **Does not hit:** retrieval quality. The guardrails constrain what may be said, not how good the search is. A perfectly safe dossier can still be a thin one.

Source: CLAUDE.md 'Guardrails'; README.md 'Guardrails'; scripts/synthesize.py (dash strip).
