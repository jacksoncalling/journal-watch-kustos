---
type: Gradient
status: live
hub: evaluative
---
# Documentation Drift

Direction: session notes accrete faster than they are reconciled. Cost: a cold reader (or model) trusts a stale line and builds the wrong picture. Threshold: already crossed in at least three places, HANDOFF says '04_feedback CONTEXT missing' and 'not a git repo' (both false now), and CLAUDE.md calls the planner nondeterminism 'the main ceiling' after the seed pin fixed it. For a single-maintainer repo whose reader is often a model, this is the sharpest production risk, and it is in the map, not the code.

pulls-on [[The Maintainer]] . pulls-on [[Query Planner]] . pulls-on [[Feedback Stage]]

- **Hits:** the next reader's trust. Every stale line is a tripwire; the map's whole value here is marking where the docs and the code disagree.
- **Does not hit:** the running system. The pipeline works regardless of the docs; drift harms the human or model who reads the docs to change it, not the code that runs.

Source: HANDOFF.md vs disk (04_feedback/CONTEXT.md exists; git history exists); CLAUDE.md vs providers.py:76.
