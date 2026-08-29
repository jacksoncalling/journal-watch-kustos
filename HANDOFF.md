# Journal Watch: Handoff / Status (2026-08-27)

Status snapshot for picking this up in a fresh session. The spec is
`~/step-into-more/projects/journal-watch/build-plan.md` (HQ). This file is the
"where we actually are" and "what's left" companion that lives with the code.

## Update 2026-08-30 (read this first, supersedes older items below)

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
