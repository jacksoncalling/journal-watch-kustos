---
type: Capability
status: live
kind: transform
hub: pipeline
---
# Synthesize

The one place judgment enters. A single LLM call writes the German brief from the selected papers. The fact line (Stufe label + links) is injected by code from a [[PMID:...]] anchor, so the model cannot inflate an evidence level or invent a link. This is the deliberate design: judgment used exactly once, everything around it deterministic. Post-processing strips em-dashes.

held-by [[The Maintainer]] . depends-on [[Rank]] . depends-on [[Provider Abstraction]] . bound-by [[The Guardrails]] . bound-by [[Brief Contract]] . governed-by [[Regulatory Boundary]] . contested-by [[Determinism vs the LLM Seam]]

- **Hits:** [[Send]] (it delivers what synthesis writes). The reader's trust: this is the only stage that could fabricate, which is why the guardrails wrap it in code.
- **Does not hit:** the evidence levels themselves. Synthesis phrases the evidence; it cannot set or raise a Stufe. That is [[Rank]]'s job, in code.

Source: scripts/synthesize.py; README.md 'How it works' step 4.
