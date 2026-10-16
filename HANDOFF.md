# Journal Watch: Handoff / Status (2026-08-27)

Status snapshot for picking this up in a fresh session. The spec is
`~/step-into-more/projects/journal-watch/build-plan.md` (HQ). This file is the
"where we actually are" and "what's left" companion that lives with the code.

## Update 2026-10-15 (read this first)

Replit ran a fictional urgent CABG + acute HIT simulation (report in the Replit
workspace at `.local/outputs/kustos-hit-evaluation.html`, not in git). All 20
PMIDs were real and all structural checks passed, yet the brief glued the
overall CHOOSE-ON result (46/49, 94 %) to the 43-patient acute-HIT subgroup,
mixed general HIT drugs into surgical advice, and missed the 2024 European
guideline. Lesson: real citations do not prove the sentence is right. We had
never measured claim accuracy, only retrieval hygiene.

Built this session (local, uncommitted):

- **Evidence saved per run.** `praxis_check.evidence_record()`; the CLI writes
  `<dossier>.evidence.json` (exact `evidence_basis` per paper, provenance,
  raw model prose, queries). `DossierResult.evidence` and the `done` stage carry
  it; the web app ignores it (no response change). **Gap: web runs save nothing.**
- **`scripts/check_claims.py`.** Deterministic number tracing. FAIL: number not
  in the cited source (dose units incl. compound mg/kg/h, mmHg and % must match;
  time units not bound), percent that the source derives as a/b tied to another
  count (the CHOOSE-ON pattern), phantom PMID in any bracket form. WARN: brief
  number not repeated in detail, percent far from its claim's numbers, uncited
  numbers, abstract-only brief not named, [VOLLTEXT] paper whose text is a stub.
  Citation in the next sentence binds. Skips small counts (no unit), years, and
  identifiers, and says how many. Checks numbers, not meaning.
- **Cold review round 1** (read-only agent, reproductions required) found 2 high
  + 6 medium holes in the first version (the CHOOSE-ON error passed clean when
  made in brief AND detail; multi-PMID briefs false-FAILed; unit, locale,
  sentence-split and citation-format gaps). All reproduced, fixed, and kept as
  regressions in `test_check_claims.py`.
- **Cold review round 2** found 2 high + 2 medium + 4 low in the rewrite (wrong
  round-thousand sample sizes passing via a decimal reading; CHOOSE-ON passing
  with "46 of the 49" phrasing; pctden false FAILs on "30-Tage", ages, trial N;
  unit spellings). Fixed: thousands-only reading before count nouns, broader
  a/b patterns, counts linked by wording (count noun + von/bei/unter) instead
  of word distance, trial N above the denominator accepted, unit aliases plus
  a WARN fallback for unknown spellings (not for small integers), numbers in
  the citation bracket checked, citation of the previous OR next sentence.
  All kept as regressions (86 cases).
- **Cold review round 3: NOT CLEAN.** Three highs fixed (CHOOSE-ON in house
  style "mit/in 43 Patienten", "n = 43"; wrong doses softened to WARN by a bare
  count, now only unit-like words count as unknown spellings; Lancet "0·87"
  decimals). Eight remaining findings kept IN as `known_failures` (expected to
  fail, they report "NOW FIXED" if they start passing). Decision (Josh,
  2026-10-16): ship the checker labelled a **screen, not proof**. Shared cause
  of all three rounds: pool-based matching (any value anywhere in the cited
  text counts). Next step for this tool is matching in context (number + unit
  + nearby words, or a calibrated claim-support judge), not more regex.
- **Quote anchoring, option A built (2026-10-16, uncommitted).** Research
  (arXiv 2609.15964, Claude Citations, MiniCheck) says: tie each claim to its
  own verbatim quote. Plan + status: `05_praxis-check/PLAN-quote-anchoring.md`.
  The model now writes `(PMID x: "quote")`; code splits quotes off before
  anything is shown, checks quote-in-paper and number-in-own-quote. Anchored
  versions of known failures M4, L7 and total-N now FAIL as they should (pool
  mode keeps them as known failures for unquoted claims). 118 offline tests.
- **Live benchmark 2026-10-16 (8 questions, runs frozen in
  `05_praxis-check/benchmark-runs/2026-10-16/`).** Europe PMC 503 outage killed
  6 of 8 on the first pass; rerun with `--only`. Gate: quoted 97 % (pass),
  verbatim 85 % (miss, bar 90 %) -> **option B (Claude Citations) per the
  gate.** Gemini edits about 11 % of its quotes (drops CIs, inserts words). No
  wrong numbers found by hand in 8 dossiers. **HIT retrieval failure:** 0 of 20
  papers on-subject, padded with off-topic reviews (bare `HIT` term, no
  surgery facet, backfill to 20). Details: `PLAN-quote-anchoring.md` status.
- **Retrieval relevance fixed (2026-10-16, uncommitted,
  `05_praxis-check/PLAN-retrieval-relevance.md`).** Ambiguous abbreviations
  (new `profile.md` block) are expanded before search; subject gate ignores
  hyphens; no off-subject padding, only up to 3 marked context guidelines;
  zero on-subject = no dossier; under 5 = code-set thin note. Replay on the
  frozen queries: HIT 0/20 -> 18/20 on-subject. `scripts/test_retrieval.py`.
  **Next:** full benchmark with synthesis (Josh's OK), then Claude Citations.
- **Where the time goes (one HIT run, 2026-10-16, now logged per stage and in
  `evidence.json` `timings`):** plan 13.7 s, search 5.0 s, rank 0.1 s, enrich
  3.7 s, synthesis 44.0 s, total 66.5 s. About 87 % is the two Gemini calls,
  not retrieval. Suspect: Gemini 2.5 Flash thinks by default (no thinking
  config in `providers.py`; thought tokens are not logged). Not yet tested.
  Note: that rerun OVERWROTE the earlier frozen HIT run in
  `benchmark-runs/2026-10-16/` (save_run now adds a time suffix instead; its
  numbers survive in `PLAN-quote-anchoring.md` and `PLAN-retrieval-relevance.md`).
- **Gemini thinking test (HIT question, single runs, 2026-10-16).** Thought
  tokens now logged; budgets settable in `profile.md` (`planer_thinking_gemini`,
  `synthese_thinking_gemini`, empty = default) or per run with
  `benchmark_praxis.py --thinking-planner 0 --thinking-synthesis 0`.
  A (planner off): plan 13.7 -> 4.8 s, and the planner wrote better queries
  (cardiac-surgery facet added). Synthesis with default thinking: 3032 thought
  tokens, 31 s, one real unsupported number ("100 Tage", not in the papers).
  B (both off, same queries and papers as A): synthesis 14.9 s, total 64 -> 43 s,
  no wrong numbers (3 FAILs: a correct CHOOSE-ON claim whose quote misses 49/43,
  one condensed quote); shorter dossier (737 vs 958 words, Kurzantwort 90 words).
  Remaining time is search (3 sequential queries, 13 to 17 s) and enrich (full
  text 10 to 12 s, many EBI 500 errors).
- **8-question run with thinking off (planner + synthesis), 2026-10-16,
  `benchmark-runs/2026-10-16/thinking-off/`.** vs today's default-thinking set:
  mean ~39 s vs ~65 s per dossier; verbatim 91 % (gate passes) vs 86 %; quote
  FAILs 16 vs 32; unsupported numbers hand-checked: 0 wrong in both (new run's 4
  are checker gaps: number words, "RR 1. 08", "0 v 20%"); 7379 vs 8481 words;
  Kurzantwort avg 103 vs 132 words (under the 120 target). **Catch:** planner
  without thinking dropped phrase quotes and added "controversy OR debate"
  facets on the corticosteroid pilot; retrieval pulled steroid-adjacent
  off-topic papers (adrenal hyperplasia, ARDS) past the subject gate, cited fell
  11 -> 5. Not a controlled comparison (baseline 7 of 8 used the old retrieval).
  `profile.md` now: planner thinking 0, synthesis thinking default.
- **Planned-query clean-up built (no LLM spend).** `clean_planned_query`
  quotes bare multi-word OR terms and drops debate-word facets (planned
  queries only). Replay on the thinking-off queries: pilot 15/16 -> 20/20
  on-subject, back on topic. Remaining relevance gap is SETTING (drug named,
  wrong clinical context: pericarditis, PONV, postpartum, ECMO); see
  `PLAN-retrieval-relevance.md` addendum.
- **Pipeline bug found, not fixed:** `enrich.fulltext_excerpt` can return a
  stub like "The content is available as a PDF (28.4 MB)." which is then
  labelled [VOLLTEXT] and sent INSTEAD of the abstract (seen in the TCI
  evidence). The checker now WARNs `thin`; the fix belongs in enrich/paper_payload.
- **`scripts/rebuild_evidence.py`** for pre-change dossiers (re-fetched,
  marked `reconstructed`). Done for the three August dossiers.
- **`scripts/test_check_claims.py`**: seeded-error cases incl. the CHOOSE-ON
  pattern and mutations of a real dossier; each also shows `verify_dossier.py`
  passing the seeded error. The dose test first FAILED (a bare "2" in the DECS
  text backed "2 mg/kg"), which led to unit-bound matching. Kept in.

First real finding: `2026-08-27-kortikosteroide-aortenklemme.md` states
"Methylprednisolon 30 mg/kg vs. 2 mg/kg" citing PMID 29732365, whose supplied
text contains neither dose (likely model background knowledge). Caveat:
reconstructed evidence.

**Next (agreed order):** must-find lists per question (landmarks + guidelines,
clinician confirms: she agreed to write an answer key for ~5 questions), then a
claim-support judge calibrated on seeded errors, then the clinician session on
applicability + omissions only. Also: save evidence from web runs; widen the
full-text excerpt (it drops methods/limitations and cuts at 8000 chars).

## Update 2026-08-30 (superseded by 2026-10-15 above)

Ran a three-tool head-to-head (OpenEvidence, Heidi, Kustos) on a clinician's own
Aortenbogen case and turned the read into a **Fields of Inquiry** map + plan
(`05_praxis-check/fields-of-inquiry-map.html`,
`05_praxis-check/PLAN-fields-of-inquiry.md`). Key reframe: what she loved (inline
tappable citations, study type at a glance) is data Kustos **already computes and
hides**; the "missing American journals" worry is **false** (`SRC:MED` is MEDLINE,
the US-run index). So the cheap wins are presentation, not new retrieval.

Two backend packages built, reviewed, and committed this session (nothing pushed;
frontend waits on Replit tokens, back 2026-09-01):

- **WP-A, citations contract (commit `13633a9`).** `rank.study_type_label()` (human
  study-type name from the same pub-type facts as the Stufe, so they never
  disagree), `praxis_check.citation_view()` (JSON-serializable per-paper objects
  built only from already-computed fields, nothing fetched), and `POST /praxis` now
  also returns `citations[]`. `dossier`/`queries`/`count` unchanged, so the CLI and
  Telegram are untouched. Contract documented in `web/REPLIT_BRIEF.md`.
- **WP-B, streaming + parallel enrich (commit `0d3e2d2`).** `build_dossier` refactored
  into a generator `dossier_stages()` that both paths drain, so nothing forks the
  guardrails. New `POST /praxis/stream` emits SSE (`searching`, `found`, `synthesis`,
  `done` | `error`) with the same auth/length gate run synchronously up front (real
  401/400/429). **Stage-streaming, not token-streaming**: the provider call blocks on
  the `refusal` stop_reason check, so `synthesis` arrives as one chunk; the early
  `searching`/`found` events carry the perceived speedup. `enrich_top()` now runs its
  independent Unpaywall + full-text round-trips in a ThreadPoolExecutor,
  allSettled-shaped (one paper's miss never sinks the batch), order/fields/counts
  unchanged.

Reviewed clean (0 critical/high; 4 low, the only one fixed was a stale comment).
`POST /praxis` is byte-compatible; benchmark and weekly scripts untouched.

**What's next (this initiative).** Frontend lane on Replit: **A4** (render inline
PMIDs as tap targets + study-type badges from `citations[]`) and **B3** (progressive
render against the SSE contract), both spec'd in `web/REPLIT_BRIEF.md` +
`PLAN-fields-of-inquiry.md`. Then the genuine-research backlog: **F4** (guidelines /
currency, sequence AFTER the `PLAN-evidence-quality.md` cited-only fix or leaks
worsen) and **F5** (format-fit by question shape). Guardrail for the frontend: render
`stufe`/`study_type`/links as-is, never recompute client-side.

## Update 2026-08-27 (superseded by 2026-08-30 above for the Praxis-Check web work)

Since the 2026-08-23 snapshot the Praxis-Check retrieval gained a **deterministic
gate layer**, the **planner was pinned**, a **cost guard** was added, and the
**web layer was verified end to end**. Freshest state is `CLAUDE.md` "Current
state"; this is the short version.

- **Gate layer** (`scripts/praxis_check.py` + a `## Domain-Gate` block in
  `profil/profile.md`): subject-actor gate (require the intervention term, not
  just context), retraction gate, MeSH negative gate (drop animal/oncology with
  no cardiac MeSH), cardiac-MeSH ranking bonus, plus synthesis guards
  (zero-citation warning, dose-directive scan) and a `dossier-vertrag` reframe
  (Kernbefund-first, tangential-endpoint exclusion). Tuned on a 7-question cardiac
  benchmark (`scripts/benchmark_praxis.py`), held on 4 more untuned questions.
- **Planner pinned** (temperature 0 + fixed seed) so the same question returns the
  same queries. Retrieval uses NO embeddings/vector store, by design.
- **Cost guard:** global daily cap (`max_dossiers_per_day` in profile.md, default
  50) enforced in `build_dossier`; ledger `05_praxis-check/usage.json`. Over the
  cap raises `DailyLimitError`, and the web app returns HTTP 429.
- **Web layer verified live** through the browser (real question -> gated, cited
  dossier, footer intact). Deploy-ready; remaining work is Replit-side config
  (Reserved VM for the 30 to 110s request, secrets).

**The "Refinements" roadmap near the bottom is DONE, do not re-implement it.**
Tighter anesthesia queries and controversy tuning are covered by the gate layer +
vertrag reframe (deterministic, not prompt-only); OA-PDF cosmetic (#7) fixed
2026-08-27 (OA-PDF vs OA-Link + DOI-duplicate suppression). A rebuild of these in
`scripts/` would duplicate or regress the verified pipeline, and any planner-prompt
change risks the determinism pin.

## TL;DR

Slice 1 (the weekly Wochenbrief) runs **end to end and was delivered live to
Telegram** on 2026-08-17. Five stages built and verified against live data:
fetch -> enrich -> rank -> synthesize -> send. As of 2026-08-23 the **orchestrator
(`run_weekly.py`) and the weekly GitHub Action (step 7) are built and verified**,
and the top correctness gap (`seen.json` cross-week dedup) is **closed**. Not yet
done: git init + first push, the private instantiation with the real profile
(step 8), RSS, and a proper code review of the new orchestrator.

## What's built and verified

| Stage | Script | State |
|---|---|---|
| Fetch | `scripts/fetch_europepmc.py` | Live-verified. Europe PMC search, dedupe, `candidates.json`. |
| Enrich | `scripts/enrich.py` | Live-verified. Unpaywall OA links + Europe PMC full text (endpoint corrected). |
| Rank | `scripts/rank.py` (+ `scripts/test_rank.py`) | Deterministic evidence levels; 12/12 mapping tests pass. |
| Synthesize | `scripts/synthesize.py` (+ `scripts/providers.py`) | Live-verified on **Gemini 2.5 Flash** (primary) with Claude Sonnet 4.6 fallback. Code injects the fact line (labels + links) from a `[[PMID:...]]` anchor, so the model cannot inflate a Stufe or invent a link. |
| Send | `scripts/send_telegram.py` | Live-verified. Splits at paper boundaries under 4096 chars, plain text, tappable links. `--whoami` finds the chat id. |
| Orchestrate | `scripts/run_weekly.py` | Verified 2026-08-23. Chains the 5 stages as subprocesses, fails loud (nonzero exit) on any stage error. Writes `seen.json` ONLY after send returns 0. `--dry-run` runs fetch..synthesize, skips send + ledger. Full `--dry-run` ran green live (Gemini brief written, nothing sent, ledger untouched). |
| Automate | `.github/workflows/weekly.yml` | Built 2026-08-23, not yet run on GitHub (repo not pushed). Cron Fri 04:00 UTC + `workflow_dispatch` (with `dry_run` input). Auto-detects live vs dry by whether Telegram secrets exist, so it copies unchanged into the private repo. Commits brief + `seen.json` only on a live run. |
| Praxis-Check | `scripts/praxis_check.py`, `05_praxis-check/`, `.github/workflows/praxis-check.yml` | **Slice 1.5, built + `--dry-run`-verified live 2026-08-23, code-reviewed + hardened 2026-08-24.** On-demand dossier. Imports and composes the slice-1 functions (fetch/enrich/rank/synthesize/send), one additive optional-param change to `search_topic` (weekly callers unaffected). All-time search (no `FIRST_PDATE`), no `seen.json`. Hybrid query building: explicit `\`\`\`query` block used verbatim, else one bounded LLM planning call. **Ranking: `sort=CITED desc` + `page_size=200` so old landmark trials surface (the plain date-default returned only the newest 50 and missed them), plus a Praxis-only title-relevance bonus so citation-sort does not float famous off-topic papers.** Deep dossier (~20 papers, `max_items` per question). `## Quellen` (Stufe + provenance + links) assembled in code; model cites inline `(PMID …)` only. `workflow_dispatch`-triggered, commits the dossier. Verified live on the pilot: surfaces the SIRS + DECS landmark RCTs and the real AF-vs-mortality controversy (Gemini Flash, ~25K in / 2.4K out tokens). |
| Web layer (mobile) | `web/app.py`, `web/index.html`, `web/requirements-app.txt`, `web/REPLIT_BRIEF.md`, `scripts/verify_dossier.py` | **Built + full-chain-verified live 2026-08-24, review-hardened 2026-08-26.** A thin OpenEvidence-style skin so the Praxis-Check can be started from a phone. `praxis_check.build_dossier(question)` is the shared callable core (CLI and web both call it, so guardrails live in one place); `question_from_text` is the in-memory seam. FastAPI: `GET /` serves the page, `POST /praxis {question,password} -> {dossier,queries,count}`. Password-gated, **fails closed** (503) if `KUSTOS_APP_PASSWORD` unset unless `KUSTOS_ALLOW_NO_AUTH=1`; `hmac.compare_digest`; question length 10..2000; `esc()` escapes quotes. Verified end to end via HTTP (106s, Hybrid LLM query planning exercised) and via `verify_dossier.py` (all 7 guardrails green on the web output). Intended host: one Replit service, no Supabase/Vercel/Render. Not yet deployed. |

Config: `profil/profile.md` (demo "Dr. Demo" profile, 3 cardiac-anesthesia
topics, provider choice, journals). `03_brief/CONTEXT.md` is the brief contract
(fed into the synthesis system prompt). Secrets in gitignored `.env`.

## How to run it (the current happy path)

One command chains all five stages and advances `seen.json` after a confirmed
send:

```bash
cd ~/journal-watch
python scripts/run_weekly.py            # full run: fetch..send, then ledger
python scripts/run_weekly.py --dry-run  # fetch..synthesize, no send, no ledger
```

Or run stages individually (each reads/writes its own JSON contract):

```bash
python scripts/fetch_europepmc.py
python scripts/enrich.py
python scripts/rank.py
python scripts/synthesize.py
python scripts/send_telegram.py
```

## Known gaps & issues (correctness first, verify these in review)

1. ~~**`seen.json` is never written -> no cross-week dedup.**~~ **FIXED
   2026-08-23.** `run_weekly.py` writes `seen.json` after a confirmed send
   (`last_run_date = today` + the delivered papers' dedupe keys). Verified: with
   a seeded ledger of 7 ids over the same window, a fresh fetch dropped 21 -> 14
   candidates, zero overlap with the ledger. If send fails, the ledger is NOT
   advanced, so those papers retry next run.
2. ~~**No orchestrator (`run_weekly.py`).**~~ **BUILT + verified 2026-08-23.**
   Chains the 5 stages, fails loud on any nonzero exit. See the stage table.
3. **Not a git repo / not on GitHub.** `git init` never run here. Step 7 (Action)
   and step 8 (private repo) both need this. Before ANY push: this is the method
   repo, keep it clean: `.env`, `candidates.json`, `selected.json`, `seen.json`
   are gitignored; confirm no real data leaks (the demo profile is fake, good).
4. ~~**`enrich.py` `_section(...)` bogus second arg.**~~ **FIXED 2026-08-23**
   (now `_section(xml, "results")`).
5. **Full-text extraction is regex tag-stripping**, not real JATS parsing.
   The non-greedy `(.*?)</sec>` also truncates at the first nested `</sec>`.
   Both are best-effort and left as-is for slice 1 (a real fix needs an XML
   parser); revisit if full-text quality matters.
   Works for excerpts; may miss sections in some article layouts. Fine for
   slice 1; revisit if full-text quality matters.
6. **Thin test coverage.** Only `test_rank.py` (evidence mapping). Fetch parsing,
   enrich, the synthesis post-processing (anchor injection, dash strip), and the
   Telegram splitter were all verified ad hoc but have no committed tests.
7. ~~**OA-PDF cosmetic:** when Unpaywall has no direct PDF, the "OA-PDF" link
   falls back to the DOI landing and duplicates the DOI link.~~ **FIXED
   2026-08-27** (`synthesize.fact_line`): a DOI-duplicate OA link is suppressed,
   and the label is OA-PDF for a real file vs OA-Link for a landing page.
8. **Telegram send** has no 429/retry handling (fine for a weekly job; note it).
9. **ICM completeness:** root `CLAUDE.md`/`README.md` router done. `CONTEXT.md`
   written for `01_fetch/` and `02_rank/` (2026-08-23). Still missing:
   `04_feedback/CONTEXT.md` (slice 1.5 stage, not built yet).

## Code review (2026-08-23, applied)

A review from the 2026-08-18 session was never recorded or applied. Re-run and
applied 2026-08-23. Fixed in `scripts/`:

- **PMID collision** (`synthesize.py`): PMID-less papers keyed on `str(None)`
  collided onto one entry; now only papers with a real PMID enter the anchor map.
- **`load_env` prefix match** (`synthesize.py`, `send_telegram.py`): now exact
  key match, so `ANTHROPIC_API_KEY_STAGING` no longer shadows `ANTHROPIC_API_KEY`
  and comment lines are ignored.
- **Label crash** (`fetch_europepmc.py`): a topic with a query but no label no
  longer crashes on `None[:44]` (label defaults to the topic id).
- **quiet-week leak** (`synthesize.py`): the quiet-week path now uses
  `paper_payload`, so internal fields (score, stufe) never reach the model.
- **Journal-trust match** (`rank.py`): normalised exact match instead of the
  fragile substring test (verified: demo ranking unchanged).
- **enrich sec-type arg** (#4 above); **em-dashes** in all docstrings/comments;
  **`schema_version`** added to `candidates.json`, `selected.json`, `seen.json`.

Two review items were NOT applied, deliberately:

- **`providers.py` refusal check was a FALSE POSITIVE.** `stop_reason ==
  "refusal"` is a real Anthropic value (Claude 4+; build-plan 5.3). The prior
  review claimed it was invalid; "fixing" it would have introduced a bug. Left
  as-is with a comment.
- **JATS nested-`</sec>` truncation** (#5 above): a regex can't parse nested XML;
  left as a documented best-effort limitation.

## Remaining work (roadmap, prioritized)

- ~~**Step 7, automation.**~~ **DONE 2026-08-23** (`run_weekly.py` +
  `.github/workflows/weekly.yml`). Not yet exercised on GitHub (repo unpushed).
- **git init + first clean push (method repo), NEXT.** No push yet. Before it:
  confirm `.env` and the run artifacts (`candidates.json`, `selected.json`,
  `seen.json`) stay gitignored, demo profile is fake (it is). The Action only
  runs once the repo is on GitHub; a `workflow_dispatch` dry-run is the first
  smoke test there.
- ~~**Code review.**~~ **DONE 2026-08-23** (see the Code review section above).
- **Step 8, private instantiation:** copy method repo -> `~/journal-watch-privat/`,
  drop in her real `profile.md` (real topics from the follow-up interview + her
  trusted journals), set `TELEGRAM_CHAT_ID` to HER chat, enable the schedule.
- **RSS** (`fetch_rss.py`): deferred; needs real feed URLs verified per journal,
  best paired with building her real profile.
- ~~**Refinements:** OA-PDF cosmetic (#7), controversy tuning, tighter
  anesthesia-focused queries.~~ **ALL DONE 2026-08-27** (see the "Update
  2026-08-27" section at the top): tighter queries + controversy handled by the
  deterministic gate layer + vertrag reframe; OA-PDF cosmetic fixed. Do not
  re-implement in `scripts/`.
- **Deploy the web app on Replit (NEXT):** reset the Replit instance onto the
  current `main` (verified, pinned, gated), then set Secrets + a Reserved VM.
- **Per-user quota:** today's cap is global; per-user fairness needs the web
  layer's user identity.
- **Evidence-quality fixes** from the Amboss vs Kustos test (2026-08-27):
  `05_praxis-check/PLAN-evidence-quality.md`. Order: strip phantom PMIDs ->
  cited-only Quellen -> Kernbefund evidence-weighting (validate) -> length ->
  off-context leaks (defer). Web deploy on Replit is DONE (backend synced to
  `main` + Replit UI redesign merged, verified live).

## Cost note

Running cost is trivial: ~6K in / 1.6K out tokens per weekly synthesis on Gemini
Flash = a fraction of a cent. The expensive part is interactive build sessions,
not the product. Keep future work scoped to discrete fresh sessions.

## Continue cheaply

A fresh session should: read this file + `build-plan.md`, run `/code-review` on
`scripts/`, then build `run_weekly.py` + the Action. Don't reload the whole
history. These two docs are the state.
