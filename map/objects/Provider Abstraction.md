---
type: Capability
status: live
kind: seam
hub: pipeline
---
# Provider Abstraction

The provider seam. Wraps Gemini 2.5 Flash (primary) with a Claude Sonnet fallback behind one interface, so synthesis and the planner call an LLM without knowing which. Crucially it sets Gemini's fixed seed=7 alongside temperature 0, applying Josh's own learning that Gemini determinism needs both. It also honours Anthropic's real 'refusal' stop_reason (a false-positive review flag, left correct on purpose).

held-by [[The Maintainer]] . holds [[Gemini / Anthropic]] . enables [[Query Planner]] . governed-by [[No Embeddings]]

- **Hits:** [[Synthesize]] and [[Query Planner]] (both route through it). Reproducibility: the seed lives here, so this file is why the pinned planner actually pins.
- **Does not hit:** [[Rank]]. Ranking never calls a provider; it is pure code. The provider seam touches only the two LLM stages.

Source: scripts/providers.py:76 (seed=7), :87 (refusal check).
