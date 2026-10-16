# Plan: Retrieval relevance (on-subject floor, ambiguous abbreviations)

Status 2026-10-16: **built and tested** (uncommitted, branch
`claim-check-screen`). Comes before Claude Citations (`PLAN-quote-anchoring.md`,
option B), by Josh's call.

**Result, retrieval replay** (frozen planner queries, live Europe PMC, no LLM;
`benchmark_praxis.py --replay-retrieval benchmark-runs/2026-10-16`):

| Question | On-subject before | After | Context guidelines |
|---|---|---|---|
| HIT / urgent CABG | 0 / 20 | 18 / 20 | EACTS 2024 CPB, STS/SCA/AmSECT CPB anticoagulation |
| other seven | 20 / 20 each | 18 to 20 / 20 | mostly EACTS 2024 CPB; none for TXA, sugammadex |

The new HIT set includes bivalirudin and argatroban during CPB, urgent on-pump
CABG with HIT, subacute HIT before surgery and the ASH 2018 HIT guideline; 13 of
20 are surgical. Still general: arterial lines, ECMO (population mismatch the
subject gate cannot see). The first replay let in two off-question cardiac
guidelines (coronary dissection, preclinical rigor); the lane now also needs a
query concept in the title, which removed the first. The rigor guideline stays
for the volatile question ("cardioprotection" is a real query concept),
labelled as context. Bare abbreviations left in queries (for the ambiguity
list, her call): CABG, CPB, DTI, AF, POAF, POD, TXA, TIVA, NIRS; of these only
POD is also an English word.

Tests: `scripts/test_retrieval.py` (20, mutation-checked: old gate, old
padding and no rewrite each fail them). Full benchmark with synthesis not yet
rerun (needs Josh's OK).

## Addendum: planned-query clean-up (2026-10-16, built)

With planner thinking off (`planer_thinking_gemini: 0`, planning 13.7 -> about
4 s) the planner wrote sloppier Booleans: bare multi-word terms (`cardiac
surgery`, which Europe PMC ANDs word by word) and "controversy OR debate"
facets. The default-thinking planner did the first too, less often.
`clean_planned_query` now quotes bare multi-word OR terms and drops facets made
only of debate words; planned queries only, never explicit ones; well-formed
queries come back unchanged (31 of 51 frozen queries). Replay on the
thinking-off queries: corticosteroid pilot 15/16 -> 20/20 on-subject, top
papers back on dexamethasone/methylprednisolone in cardiac surgery; other
questions unchanged. Tests in `test_retrieval.py` (`query_cleanup`).

**Still open, the next relevance lever: setting.** The subject gate checks that
a paper names the drug, not that it is about her setting. Left in after all
fixes: tuberculous pericarditis (prednisolone), a PONV Cochrane review
(dexamethasone), postpartum haemorrhage (TXA), ECMO and catheter-patency papers
(HIT). A setting check (cardiac-surgery MeSH or context-facet terms in
title/abstract, scored or gated) would address these.

## What broke (HIT benchmark question, `benchmark-runs/2026-10-16/`)

0 of 20 selected papers were on-subject; the model still wrote 793 words.
Three causes stacked:

1. **Bare `HIT` in the query.** Europe PMC search ignores case, so `HIT`
   matches the English word "hit". The citation-sorted pool of 200 fills with
   famous papers that contain "hit" (fibrates, ARDS, stents).
2. **Hyphen blind spot in the subject gate.** The subject concept was
   `heparin induced thrombocytopenia`; abstracts write `heparin-induced`. The
   gate is a plain substring test, so even real HIT papers failed it.
3. **Padding to 20.** `selected = (on + off)[:20]` backfills off-subject papers
   whenever the on-subject set is short, here with all 20 slots.

## Changes

**1. Ambiguous abbreviations never go into a search bare.** New block in
`profile.md` (controlled vocabulary, owned by her and Josh): abbreviation ->
spelled-out phrase(s), for abbreviations that are also ordinary words (HIT,
ACT, MAP, BIS, PE). After planning, code rewrites any unquoted occurrence in
a query into the quoted expansion. Applies to explicit queries too (with a
note). The planner prompt is left unchanged on purpose, so all other benchmark
queries stay comparable; code enforces, the prompt is not trusted to.

**2. Subject gate normalises hyphens and spacing** on both sides, so
`heparin-induced` = `heparin induced` (same for `del-Nido`, `cross-clamp`).

**3. Floor instead of padding.**
- Off-subject papers no longer fill the slots.
- One exception, a small **context-guideline lane**: up to 3 off-subject
  papers that are guidelines (pub type) AND carry cardiac-context MeSH. Broad
  guidelines often do not name the specific condition (the 2024 EACTS CPB
  guideline in the HIT case), and Replit's audit flagged exactly that miss.
  They are marked to the model as context, not as evidence for the question,
  and the vertrag says so.
- **0 on-subject papers: no dossier.** `PraxisError` ("keine Paper zum Thema
  der Frage"), which the web app already shows as "Keine Belege gefunden".
  No answer is safer than a confident answer from unrelated papers.
- **Fewer than 5 on-subject papers:** the dossier gets a code-set note under
  the title ("Nur N Paper behandeln das Thema der Frage direkt ..."), and the
  synthesis is told the count.

## How we know it works

- Offline tests with synthetic candidates: hyphen match, rewrite of bare
  `HIT` (and not inside quotes or inside other words), no padding, guideline
  lane cap and MeSH condition, zero-floor error, thin-floor note.
- **Retrieval replay without any LLM call:** take the planner queries saved in
  each `benchmark-runs/2026-10-16/*.evidence.json`, apply the rewrite, run the
  real Europe PMC search, filters, ranking and selection, and compare the
  on-subject count and selected titles with the frozen run. Europe PMC only, no
  model cost.
- The full benchmark (with synthesis) can follow later, only with Josh's OK.

## Risks

- A subject gate that is too strict now yields an EMPTY dossier instead of a
  padded one. That is the intended trade (visible failure over silent wrong
  context), but questions whose subject term the planner phrases oddly may stop
  answering. The replay shows how often.
- The ambiguity list is hand-kept. A new ambiguous abbreviation passes until it
  is added; the replay output lists bare short abbreviations for review.
- The guideline lane can still admit a cardiac guideline that is off-question;
  it is capped at 3, labelled as context, and its claims still go through the
  claim check.
