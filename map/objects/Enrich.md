---
type: Capability
status: live
kind: transform
hub: pipeline
---
# Enrich

The second stage. Adds open-access links (Unpaywall) and legal OA full text (Europe PMC) to each candidate. Its independent per-paper round-trips run in a ThreadPoolExecutor, allSettled-shaped, so one paper's miss never sinks the batch (Josh's parallel-AI learning, applied). Full-text extraction is best-effort regex tag-stripping, not real JATS parsing, a known limitation.

held-by [[The Maintainer]] . depends-on [[Fetch]] . bound-by [[The Guardrails]]

- **Hits:** [[Rank]] and [[Synthesize]] (they read the OA links and full text). The [VOLLTEXT]/[NUR ABSTRACT] provenance label downstream.
- **Does not hit:** [[Fetch]]'s candidate set. Enrich annotates papers; it never adds or removes them from the pool.

Source: scripts/enrich.py; HANDOFF.md gap #5 (JATS limitation).
