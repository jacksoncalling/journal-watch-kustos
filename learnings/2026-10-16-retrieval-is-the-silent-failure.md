---
date: 2026-10-16
project: journal-watch
category: gotcha
tags: [retrieval, search-queries, relevance, rag]
---

## What Happened

For the HIT question 0 of 20 selected papers were on-topic. Bare `HIT` in the
query matched the English word "hit" (Europe PMC ignores case); the subject
gate missed "heparin-induced" because the query said "heparin induced"; and the
code padded all 20 slots with famous unrelated papers. The model still wrote
793 confident words from them.

## What We Learned

The writer never says "these sources do not fit". Bad retrieval produces a
polished wrong answer, which is more dangerous than a writing error and
invisible to any quote check (the quotes would be correct). Model-planned
queries also drift: without "thinking" the planner dropped phrase quotes
(`cardiac surgery` searched as two loose words) and added "controversy OR
debate" facets that filter for papers using those words.

## How to Apply It

Expand ambiguous abbreviations in code; normalise hyphens before matching
terms; make the result count a cap, not a target; stop when nothing matches;
clean planned queries in code (quote multi-word terms, drop debate-word facets).
Then check the SETTING of the papers, not just the topic (still open: drug
named, wrong clinical context).

## Files / Context

`05_praxis-check/PLAN-retrieval-relevance.md`, `scripts/test_retrieval.py`,
`profil/profile.md` ("Mehrdeutige Abkürzungen"), replay with
`scripts/benchmark_praxis.py --replay-retrieval`.
