# Plan: Quote-anchored synthesis (Praxis-Check)

Status 2026-10-16: **option A built and tested offline** (uncommitted, branch
`claim-check-screen`). Decision (Josh): A first with the measured gate to B.
Built: quote rule in `dossier-vertrag.md`, anchors split off right after
synthesis in `praxis_check.dossier_stages` (display and web stream see plain
`(PMID ...)`), `anchors` + raw prose in `evidence.json`, anchored mode in
`check_claims.py`, 23 offline tests (mutation-checked), benchmark reports
anchored/verbatim shares, saves every run to `benchmark-runs/<date>/` and
prints the gate verdict. HIT question added as benchmark item 8.

**Live result (8 questions, Gemini 2.5 Flash, runs frozen in
`benchmark-runs/2026-10-16/`, re-check free with `--recheck`):**

- Quoted: 197 of 204 cited claims (97 %, bar 95 %): passes.
- Verbatim: 186 of 220 quotes (85 %, bar 90 %): **misses. Gate says build B.**
  Of the 34 misses, 12 differ only in punctuation or spacing, 25 are real edits
  (dropped confidence intervals, inserted words such as "95% confidence
  interval", a silently removed middle part). Tolerating punctuation would land
  at about 90 %, exactly on the bar, and punctuation includes minus signs and
  decimal points, so that tolerance is not safe to add just to pass.
- Numbers: 50 claim numbers are in the paper but outside their quote (quote too
  short, claim fine). 11 were "not in the paper"; checked by hand, none is a
  wrong number: 4 number words in the source, 2 rounded ("über 3000" for 3079),
  1 sum (431 + 437), 2 checker bugs (value-CI-unit, fixed), 2 units the model
  added that the abstract does not state ("590 vs 820 ml").
- Checker bugs found on live data and fixed with regression tests: HTML-tag
  stripping ate "p<0.01 ... >18", four-dot ellipsis, "1.2 (0.9-1.9) ng/dL".
- Separate, bigger finding: the HIT question retrieved 0 on-subject papers
  (bare `HIT` in the query, no cardiac-surgery facet); the 20 slots were padded
  with highly cited off-topic reviews and the model still wrote 793 words.

Open questions 3 to 5 below are still open.

## Why

`check_claims.py` searches a claim's numbers in the whole cited text (pool
matching). Three cold-review rounds kept finding wrong numbers that pass
because the same value appears somewhere else in the paper. The field ties
each claim to its own passage instead: claim plus verbatim quote, a string
check that the quote exists, then a judge for support (arXiv 2609.15964;
Claude Citations; MiniCheck-style checkers on claim/passage pairs).

**Goal:** every load-bearing claim points at one passage of the evidence the
model actually saw. Code checks deterministically that the passage exists
and that the claim's numbers stand in that passage. What she reads stays as
it is today.

## Decision 1: mechanism

| | A. Quote marker in the contract | B. Claude Citations API |
|---|---|---|
| Provider | Gemini primary + Claude fallback, both | Synthesis must move to Claude; Gemini fallback produces no anchors |
| Quote exists? | Not guaranteed; checked by code, so measurable | Guaranteed valid pointer + char offsets |
| Granularity | Model picks the span (5 to 40 words) | Whole source sentences (auto chunking) |
| Code change | Contract rule, anchor parsing in `finalize`, checker mode | New request shape (one document per paper), parse text+citation blocks, code inserts `(PMID ...)`; contract loses the PMID rule |
| Cost / latency | More output tokens (quotes) on Flash | Claude price above Flash; `cited_text` not billed as output |
| Still needs the checker? | Yes (existence + numbers) | Yes (numbers in passage; existence is free) |

C (both paths) is rejected: two synthesis implementations break the
"one guarded pipeline" rule.

**Recommendation: A first, with a measured gate to B.** Smallest change, keeps
the vertrag as the single writing rule and the provider swappable, and the
deterministic checker is needed under B too. A also produces the number that
decides B. **Gate:** on the benchmark, at least 95 % of load-bearing claims
anchored and at least 90 % of quotes verbatim. Below that, build B.

## Decision 2: marker format (A)

Model writes, after each load-bearing claim:

    (PMID 12345678: "exact words copied from evidence_basis")
    (PMID 111: "quote one"; PMID 222: "quote two")

Contract rules: copy verbatim from `evidence_basis`, in the source language
(never translated), 5 to 40 words, one `...` allowed to join two parts of the
same sentence, and the quote must contain every number the claim states.
Kurzantwort claims carry their own quotes.

**Gotcha:** `finalize` runs `strip_dashes`, and sources contain en dashes
(`0.59–0.82`). Anchors must be parsed out of the raw body BEFORE
`strip_dashes`/`strip_model_labels`, or the quotes stop being verbatim. The
dash rule applies to displayed prose; quotes are never displayed.

## Deterministic checks (`check_claims.py`, anchored mode)

Per anchored claim:

1. **Quote in source** (FAIL): normalized substring of that PMID's
   `evidence_basis` (whitespace, case, unicode dashes and minus, middle dot,
   quote marks); with `...` each part must match, in order.
2. **Quote length** (WARN): under 5 words, or over 60 words / 400 chars
   (quoting half an abstract is the pool again through the back door).
3. **Numbers in own quote** (FAIL): every claim number, with today's value and
   unit rules, must stand in the claim's own quote. The pctden rule runs on
   the quote. This is the structural fix for the open holes: CHOOSE-ON ("43"
   is not in "46 of 49 patients (94%)"), M4 (ratio elsewhere in the paper),
   L7 (neighbour paper), and the total-N limit (241 is not in the quote).
4. **Unanchored claim** (WARN): sentence with a PMID but no quote. Falls back
   to today's pool screen, reported as "screened, not anchored".
5. **Brief vs detail**: compared by quote, not by loose number pools.
6. **Coverage line**: anchored share, verbatim share, numbers checked in
   quote vs in pool.

Not deterministic, and a separate later step: does the quote *support* the
claim (population, setting, strength). That is a judge on (claim, quote)
pairs, calibrated on our seeded errors and her answer key. Anchoring is its
precondition.

## Keeping quotes out of what she reads

- `finalize` parses the anchors from the raw model body, stores them in
  `evidence.json` under `claims` (section, display sentence, PMIDs, quotes,
  source char span found by code), then rewrites each marker to
  `(PMID 111, 222)`. After that the existing steps run unchanged
  (dash strip, Quellen, footer).
- Dossier `.md`, Telegram and web look exactly as today; `verify_dossier.py`
  and the web PMID parser need no change. `synthesis_raw` keeps the markers
  for audit.
- **Optional later, her call:** the web tap-preview could show the anchored
  passage instead of the first 240 characters of the abstract. That is the
  OpenEvidence behaviour she liked, but it shows English quotes on purpose.
  Default: off.

## Failure policy (staged)

1. **Warn-only** (as now): measure rates on the benchmark.
2. **After calibration, decide:** add a visible line to the dossier ("n
   Aussagen ließen sich nicht am gelieferten Text belegen") or drop failing
   claims (the CLAUDE.md guardrail says "drop unsupported claims", but cutting
   sentences out of prose can leave it incoherent). No second LLM call to
   repair, per the one-synthesis-call rule.

## Measurement and acceptance

- **Offline tests first** (no API cost): anchored fixtures for correct quote,
  paraphrased quote, quote from the wrong paper, translated quote, CHOOSE-ON
  with quote, number not in quote but elsewhere in the paper, en dash in the
  quote, multi-PMID group, ellipsis. Promote the `known_failures` that
  anchoring fixes (M4, L7, total-N) into regressions. New tests must fail on
  today's code.
- **Live** with `--dry-run`: the 7-question benchmark plus the HIT question.
  Report anchored %, verbatim %, number-in-quote FAILs, extra words and
  tokens, latency. About 8 synthesis + 8 planner calls on Gemini Flash.
- Fresh cold review after the build, reproductions required.
- Apply the gate to decide A or B.

## Files

Touched for A: `05_praxis-check/dossier-vertrag.md` (anchor rule),
`scripts/praxis_check.py` (`build_user` instruction, anchor parsing in
`finalize`, `claims` in `evidence_record`), `scripts/check_claims.py`
(anchored mode), `scripts/test_check_claims.py`, `scripts/benchmark_praxis.py`
(anchoring metrics), `CONTEXT.md`, `HANDOFF.md`.
Not touched: retrieval, ranking, Quellen assembly, `web/index.html` (unless the
preview option is chosen), the weekly brief path in `synthesize.py`.

## Risks

- **Gemini Flash quoting compliance is unknown.** Published compliance ranges
  from over 90 % to about 13 % depending on the model. The gate handles it.
- **More output, longer runs.** Runs already take 60 to 90 s; quotes add
  tokens. Prose quality could drop if attention goes to quoting. Measure.
- **Longer contract** may weaken other rules (dose framing, Kurzantwort
  length). The existing benchmark metrics catch regressions there.
- **Right numbers, wrong meaning.** A quote can contain the claim's numbers in
  a different sense. Residual; that is the judge's job.
- **Web runs still save no evidence.** Her real runs on Replit would never be
  checked. Needs its own decision (where evidence lands on Replit).

## Open questions (Josh)

1. A first with the gate to B, or straight to Claude Citations?
2. OK to spend the benchmark runs (about 16 Gemini calls)?
3. Anchored passage in the web tap-preview later, or strictly hidden?
4. Failure policy after measurement: visible note, or drop?
5. Where should web-run evidence be stored?
