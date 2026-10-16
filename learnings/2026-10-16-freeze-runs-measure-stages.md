---
date: 2026-10-16
project: journal-watch
category: workflow
tags: [benchmarking, latency, reproducibility, gemini]
---

## What Happened

Dossiers took 65 to 90 s and we assumed the live search was the bottleneck.
Per-stage timing showed about 87 % was the two Gemini calls. Gemini 2.5 Flash
"thinks" by default, unconfigured and unlogged; turning it off brought runs to
about 39 s. One same-day rerun overwrote a frozen benchmark run, and that file
is lost.

## What We Learned

Saving exactly what the model saw on every run makes re-measuring free: a
checker fix is re-tested with `--recheck`, a retrieval change with
`--replay-retrieval`, without any AI call. Speed fixes trade against quality
(the planner without thinking wrote sloppier queries), so measure both, and a
comparison where several things changed at once is not controlled.

## How to Apply It

Log per-stage time and hidden thinking tokens before optimising anything.
Freeze inputs and outputs of every eval run under a unique name, never
overwrite one. Change one variable per comparison, or say plainly that it is
not controlled.

## Files / Context

`scripts/benchmark_praxis.py` (`--recheck`, `--replay-retrieval`, `--label`,
`--thinking-planner`, `--thinking-synthesis`), `evidence.json` `timings`,
`profil/profile.md` (`planer_thinking_gemini`, `synthese_thinking_gemini`).
