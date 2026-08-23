# Journal Watch — Handoff / Status (2026-08-23)

Status snapshot for picking this up in a fresh session. The spec is
`~/step-into-more/projects/journal-watch/build-plan.md` (HQ). This file is the
"where we actually are" and "what's left" companion that lives with the code.

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

Config: `profil/profile.md` (demo "Dr. Demo" profile — 3 cardiac-anesthesia
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

## Known gaps & issues (correctness first — verify these in review)

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
   repo, keep it clean — `.env`, `candidates.json`, `selected.json`, `seen.json`
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
7. **OA-PDF cosmetic:** when Unpaywall has no direct PDF, the "OA-PDF" link falls
   back to the DOI landing and duplicates the DOI link. Suppress or relabel when
   `url_for_pdf` is absent.
8. **Telegram send** has no 429/retry handling (fine for a weekly job; note it).
9. **ICM completeness:** missing root `CLAUDE.md`/`README.md` router and the
   `CONTEXT.md` contracts for `01_fetch/`, `02_rank/`, `04_feedback/` (plan §4).
   The pipeline runs without them, but the workspace isn't fully "walkable" yet.

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

- ~~**Step 7 — automation.**~~ **DONE 2026-08-23** (`run_weekly.py` +
  `.github/workflows/weekly.yml`). Not yet exercised on GitHub (repo unpushed).
- **git init + first clean push (method repo), NEXT.** No push yet. Before it:
  confirm `.env` and the run artifacts (`candidates.json`, `selected.json`,
  `seen.json`) stay gitignored, demo profile is fake (it is). The Action only
  runs once the repo is on GitHub; a `workflow_dispatch` dry-run is the first
  smoke test there.
- ~~**Code review.**~~ **DONE 2026-08-23** (see the Code review section above).
- **Step 8 — private instantiation:** copy method repo -> `~/journal-watch-privat/`,
  drop in her real `profile.md` (real topics from the follow-up interview + her
  trusted journals), set `TELEGRAM_CHAT_ID` to HER chat, enable the schedule.
- **RSS** (`fetch_rss.py`): deferred; needs real feed URLs verified per journal,
  best paired with building her real profile.
- **Refinements:** OA-PDF cosmetic (#7), controversy tuning, tighter
  anesthesia-focused queries (broad "cardiac surgery" queries pulled some
  basic-science papers).

## Cost note

Running cost is trivial: ~6K in / 1.6K out tokens per weekly synthesis on Gemini
Flash = a fraction of a cent. The expensive part is interactive build sessions,
not the product. Keep future work scoped to discrete fresh sessions.

## Continue cheaply

A fresh session should: read this file + `build-plan.md`, run `/code-review` on
`scripts/`, then build `run_weekly.py` + the Action. Don't reload the whole
history — these two docs are the state.
