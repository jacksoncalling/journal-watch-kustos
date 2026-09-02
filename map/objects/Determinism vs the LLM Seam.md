---
type: Tension
status: live
hub: evaluative
---
# Determinism vs the LLM Seam

The design's central pull. Kustos stakes its trustworthiness on being deterministic code everywhere, so guardrails and provenance hold no matter what the model does. But two seams must use an LLM: the query planner and synthesis. Pinning (temp 0 + seed 7) buys reproducibility, yet Gemini's seed is best-effort and Europe PMC's corpus drifts underneath, so the benchmark is 'mostly' not 'provably' a regression gate. Both sides are live now: you cannot remove the LLM (a human question must become a query) and you cannot fully pin it.

contests [[Query Planner]] . contests [[Synthesize]] . contests [[Cardiac Benchmark]] . contests [[Europe PMC]]

- **Hits:** the whole production-readiness verdict. It decides whether the benchmark can ever be a hard CI gate.
- **Does not hit:** the [[No Embeddings]] decision, which is settled. The tension is not about vectors; it is about the irreducible judgment seam that remains after you have removed them.

Source: praxis_check.py:205 (temp 0); providers.py:76 (seed 7); CLAUDE.md known-issue #1.
