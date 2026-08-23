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
| 01 fetch | `scripts/fetch_europepmc.py`, `scripts/enrich.py` |
| 02 rank | `scripts/rank.py` (+ `test_rank.py`) |
| 03 brief | `03_brief/CONTEXT.md`, `scripts/synthesize.py`, `scripts/providers.py` |
| 04 feedback | `04_feedback/` (slice 1.5) |
| Orchestrator + weekly cron | `scripts/run_weekly.py`, `.github/workflows/weekly.yml` |
| GitHub | https://github.com/jacksoncalling/journal-watch-kustos |

## Current state (2026-08-23)

Slice 1 (the Wochenbrief) is built, code-reviewed, and pushed to GitHub. Pipeline
fetch, enrich, rank, synthesize, send is chained by `run_weekly.py`; `seen.json` is
written only after a confirmed send. Gaps and history live in `HANDOFF.md`.

**Next build: the Praxis-Check (slice 1.5), the on-demand search.** Second artifact
type and her strongest need. A fresh window can start here directly (below).

## Next build: Praxis-Check (the search function)

Occasion-driven, not weekly: "for procedure/decision X, what is the current
evidence, what is standard, where is the controversy?" One dossier per question.
Full spec: `build-plan.md` §7. Origin and pilot question: `interview-1.md` (Lesart
point 2, and open point 4).

First moves, reusing the slice-1 pipeline (do not rebuild it):
1. Scaffold `05_praxis-check/` as an ICM stage: a `CONTEXT.md` contract, a `fragen/`
   input folder (one Markdown question per file), an `output/` for dossiers.
2. Write a script that reuses fetch/rank/synthesize with a deeper, non-windowed
   search per question (drop the `FIRST_PDATE` weekly window, widen results, swap the
   weekly-brief prompt for a dossier prompt).
3. Trigger by `workflow_dispatch`; deliver the dossier via Telegram and commit it.

**Build it the ICM way.** Invoke `/icm-architect` when designing the stage and follow
its invariants: one folder one job, a `CONTEXT.md` naming inputs, process, outputs and
the human check, numbered order, factory (prompts, schema) kept apart from product
(dossiers). Once scaffolded, the full stage contract lives in `05_praxis-check/CONTEXT.md`,
not here.

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
```

Secrets in gitignored `.env` (see `.env.example`): `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Workflow rules

- ICM workspace: truth is small and singular (`profile.md`, `kanon.md`, the briefs and
  dossiers); generated views are disposable. Keep this file thin; new content lives in the
  stage folder it belongs to, with a pointer here.
- LLM judgment is used once per artifact (synthesis). Everything else is deterministic code.
- Not a git repo behavior note: commit and push only when asked.
