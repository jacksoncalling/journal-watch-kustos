# CLAUDE.md · Kustos (journal-watch)

Root router for this **ICM workspace**. Small on purpose: it points at everything
and holds almost nothing. Read this first, then open only what the task needs.

**What this is:** a weekly German medical-literature digest ("Wochenbrief") for one
clinician, plus an on-demand research search (the Praxis-Check). The folder is the
database: config, memory, and every brief live as files in this repo. Story:
[README.md](README.md). Full spec (HQ): `../step-into-more/projects/journal-watch/build-plan.md`.

## Where things live

| Need | Go to |
|---|---|
| Live status, gaps, roadmap | `HANDOFF.md` (read right after this file) |
| The spec, settled decisions | `../step-into-more/projects/journal-watch/build-plan.md` |
| Why she needs it (interview) | `../step-into-more/projects/journal-watch/interview-notes/2026-08-16-interview-1.md` |
| Config: topics, journals, provider | `profil/profile.md` (demo "Dr. Demo") |
| Learned memory | `profil/kanon.md` |
| 01 fetch | `01_fetch/CONTEXT.md`, `scripts/fetch_europepmc.py`, `scripts/enrich.py` |
| 02 rank | `02_rank/CONTEXT.md`, `scripts/rank.py` (+ `test_rank.py`) |
| 03 brief | `03_brief/CONTEXT.md`, `scripts/synthesize.py`, `scripts/providers.py` |
| 04 feedback | `04_feedback/` (slice 1.5) |
| 05 praxis-check | `05_praxis-check/CONTEXT.md`, `05_praxis-check/dossier-vertrag.md`, `scripts/praxis_check.py` |
| Orchestrator + weekly cron | `scripts/run_weekly.py`, `.github/workflows/weekly.yml` |
| GitHub | https://github.com/jacksoncalling/journal-watch-kustos |

## Current state (2026-08-23)

Two artifact types are built. **Slice 1 (the Wochenbrief):** fetch, enrich, rank,
synthesize, send, chained by `run_weekly.py`; `seen.json` written only after a
confirmed send; weekly cron. Code-reviewed, pushed to GitHub. **Slice 1.5 (the
Praxis-Check):** the on-demand dossier, built 2026-08-23. It reuses the slice-1
functions by import (no rebuild, weekly scripts untouched), searches all-time per
question, and writes one dossier per question. Triggered by `workflow_dispatch`,
not cron. Full stage contract: `05_praxis-check/CONTEXT.md`. Gaps and history:
`HANDOFF.md`. `01_fetch` and `02_rank` now carry `CONTEXT.md`; `04_feedback` still
lacks one.

## Guardrails (non-negotiable, from build-plan §3)

- **No dosage recommendations.** A study may be summarized and doses named, but never a
  dose held up as advice. The Fußzeile stays: "Immer Originalquelle und Klinikstandard prüfen."
- **No paywall circumvention.** Every item carries its DOI; she opens it with her own access.
- **No patient data** in queries, files, or messages.
- **Every claim carries provenance.** Evidence level and `[VOLLTEXT]`/`[NUR ABSTRACT]` are
  set in code from publication type, never by the model. Drop unsupported claims.
- **Regulatory boundary.** Personal tool for one clinician, not a marketed product.
  Becoming a hospital offering enters EU AI Act high-risk (clinical decision support). Out of scope.
- **No em-dashes or en-dashes** as punctuation, in generated text or in docs. Enforced in the
  synthesis prompt and in `synthesize.py` post-processing. German compound hyphens are fine.

## Run it

```bash
python scripts/run_weekly.py            # full weekly run
python scripts/run_weekly.py --dry-run  # fetch..synthesize, no send, no ledger

python scripts/praxis_check.py            # dossier for the newest fragen/*.md
python scripts/praxis_check.py --dry-run  # fetch..synthesize, write, no send
python scripts/praxis_check.py --plan-only  # resolve + print the search query
```

Secrets in gitignored `.env` (see `.env.example`): `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Workflow rules

- ICM workspace: truth is small and singular (`profile.md`, `kanon.md`, the briefs and
  dossiers); generated views are disposable. Keep this file thin; new content lives in the
  stage folder it belongs to, with a pointer here.
- LLM judgment over content is used once per artifact (synthesis). Everything else is
  deterministic code. One bounded exception: the Praxis-Check's Hybrid query building may
  add a second LLM call that only translates the question into a search string (never a
  clinical claim), and only when the question file carries no explicit `query` block.
- Not a git repo behavior note: commit and push only when asked.
