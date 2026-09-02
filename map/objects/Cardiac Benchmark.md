---
type: Capability
status: leftover
kind: eval harness
hub: verification
---
# Cardiac Benchmark

A 7-question cardiac-anaesthesia benchmark (benchmark_praxis.py, her real domain from Interview 1) that tuned the gate layer: offsub 0/20, 0 phantom citations, 0 dose-directives, controversy present on all 7. It runs and it shaped the gates, but by the system's own account it 'is not yet a clean regression gate', so it is honest residue: a real eval that does not yet gate CI. Leftover, not live.

evaluates [[Gate Layer]] . evaluates [[Query Planner]] . depends-on [[Praxis-Check]] . contested-by [[Determinism vs the LLM Seam]]

- **Hits:** confidence in the [[Gate Layer]]. If wired into CI against the pinned planner, it becomes the regression gate the production question is really asking for.
- **Does not hit:** the weekly [[Rank]], which has its own separate unit tests (test_rank). The benchmark scores the on-demand dossier, not the weekly brief.

Source: scripts/benchmark_praxis.py; CLAUDE.md known-issues ('not yet a clean regression gate').
