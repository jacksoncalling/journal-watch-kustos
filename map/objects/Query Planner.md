---
type: Capability
status: live
kind: llm seam
hub: retrieval-layer
---
# Query Planner

The one nondeterministic seam, now pinned. When a question file carries no explicit query block, one bounded LLM call translates the German question into a Europe PMC boolean query. It runs at temperature 0 (praxis_check.py:205) and, through the provider seam's seed=7, is reproducible run to run. The docs disagree about this: HANDOFF calls it pinned, CLAUDE.md still calls its nondeterminism 'the main ceiling'. The code settles it, the pin is real.

held-by [[The Maintainer]] . enabled-by [[Provider Abstraction]] . feeds [[Fetch]] . contested-by [[Determinism vs the LLM Seam]] . would-be-fed-by [[Abbrev-MeSH Expansion]]

- **Hits:** [[Fetch]] (it produces the query Fetch runs). [[Cardiac Benchmark]] repeatability. Whether the whole dossier is a clean regression target.
- **Does not hit:** [[Synthesize]]'s determinism. Pinning the planner does not pin the dossier call; synthesis keeps a non-zero temperature on purpose.

Source: scripts/praxis_check.py:201-205; scripts/providers.py:76; CLAUDE.md known-issue #1 (stale).
