---
type: Jurisdiction
status: live
kind: legal envelope
hub: contracts
---
# Regulatory Boundary

The authority envelope that decides what Kustos is allowed to be. Under the MDR (2017/745), software is a medical device when its declared intended purpose is medical; the AI Act (2024/1689) stacks high-risk on top only once it is already a device. MDCG 2019-11 draws the line: retrieving and citing literature is a library function; answering a question about the patient in front of the clinician is decision support, a device. Kustos is deliberately built to sit below that threshold. Crossing it is what made OpenEvidence leave the EU.

governs [[The Guardrails]] . governs [[Synthesize]] . governs [[Dossier-Vertrag]] . contested-by [[Library vs Decision Support]]

- **Hits:** [[The Guardrails]], the [[Dossier-Vertrag]], and every framing choice. The single decision 'is the intended purpose medical' governs the whole product's legal existence.
- **Does not hit:** the code's correctness. The boundary is about declared purpose, not implementation; you can cross it with the same code by changing only how you describe it.

Source: README.md 'Regulatory boundary'; CLAUDE.md 'Guardrails' (MDR/AI Act).
