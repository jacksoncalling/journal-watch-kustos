---
date: 2026-10-16
project: journal-watch
category: pattern
tags: [claim-verification, citations, evals, llm-output]
---

## What Happened

Kustos cited a real paper (CHOOSE-ON) but wrote "94% in 43 patients"; the
paper says 46 of 49 (94%), and 43 is a subgroup. Every structural check passed,
because none of them looked at the claim, only at whether the paper exists.

## What We Learned

A citation existing proves nothing about the sentence attached to it. What
works: tie each claim to a verbatim quote, then check deterministically that
the quote is in the paper and that every number of the claim stands in its OWN
quote. Matching numbers against the whole paper ("pool matching") let wrong
numbers pass through three cold-review rounds.

Percentages from a checker mix three things: model errors, checker errors (a
hyphen, "p<0.01 ... >18" read as an HTML tag, "Thirty-two" as a word, "0 v 20%")
and harmless differences (an added bracket). Behind a "15 % of quotes failed"
figure, hand-sorting found 0 wrong numbers in 16 dossiers.

## How to Apply It

Demand quote anchors for any AI answer built from documents. Never report a
failure rate before opening every failure once by hand and sorting it into
model / checker / harmless.

## Files / Context

`scripts/check_claims.py`, `scripts/test_check_claims.py`,
`05_praxis-check/PLAN-quote-anchoring.md`, runs in
`05_praxis-check/benchmark-runs/2026-10-16/`.
