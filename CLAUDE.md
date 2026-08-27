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

## Current state (Updated 2026-08-27)

**What's working.** Both artifact types ship. **Slice 1 (Wochenbrief):** fetch,
enrich, rank, synthesize, send, chained by `run_weekly.py`; weekly cron;
code-reviewed, pushed. **Slice 1.5 (Praxis-Check):** on-demand dossier, reuses
slice-1 functions by import (weekly scripts untouched), all-time search per
question. This session added a **deterministic gate layer** to the Praxis-Check
retrieval, tuned against a new 7-question cardiac-anaesthesia benchmark
(`scripts/benchmark_praxis.py`, questions inline, her real domain from Interview
1). The layers, all in `praxis_check.py` + a `## Domain-Gate` block in
`profile.md`: (1) subject-actor gate (require the intervention term, not just
context) with a soft on/off partition + backfill; (2) retraction gate (drop
`Retracted Publication` / `Retraction of Publication`); (3) MeSH negative gate
(hard-drop animal/oncology records with no cardiac MeSH; ~150 dropped across the
7 questions, zero per-question tuning); (4) cardiac-MeSH ranking bonus (+40,
surfaced the NEJM MYRIAD trial that earlier runs buried); (5) synthesis guards
(zero-citation warning, dose-directive scanner) + vertrag reframe (Kernbefund
first, evidence-attributed not advice; tangential-endpoint exclusion). Benchmark
result: offsub 0/20, 0 phantom, 0 dose-directives, controversy present on all 7;
tier mix now reads as honest thin-vs-thick evidence rather than false breadth.
**Retrieval uses NO embeddings/vector store by design** (boolean Europe PMC +
deterministic scoring + string/MeSH matching; only the query planner and
synthesis are LLM calls). Full stage contract: `05_praxis-check/CONTEXT.md`.
Gaps and history: `HANDOFF.md`. `04_feedback` still lacks a `CONTEXT.md`.

**Known issues.** (1) **Planner nondeterminism** is now the main ceiling: the
LLM query planner returns different queries every run (one run produced a 0-hit
query), so the benchmark is not yet a clean regression gate. (2) **Human
off-context leaks** survive the gates (e.g. the WOMAN obstetric TXA trial ranked
into the TXA question): the negative gate only catches animal/oncology, so a
human paper in the wrong specialty passes the subject gate and merely sinks. (3)
This session's changes are **uncommitted**; `05_praxis-check/CONTEXT.md` still
describes the pre-gate ranking and should be refreshed.

**What's next.** (1) **Pin the planner + add a deterministic MeSH synonym layer.**
Set the planner to temperature 0 / fixed model for reproducibility, AND add a
controlled-vocabulary block to `profile.md` mapping her domain's abbreviations to
full MeSH entry terms (TCI -> target-controlled infusion; TIVA -> total
intravenous anaesthesia; ABW -> adjusted/corrected body weight; TXA -> tranexamic
acid; NIRS -> near-infrared spectroscopy; ...), expanded into queries before
search. This is the "controlled vocabulary" layer of the Ontology Pipeline
(Talisman): MeSH is already a professionally maintained medical thesaurus, so we
consume it, we do not build a graph. Deterministic abbrev->term expansion also
directly cuts the planner nondeterminism that is the current ceiling. (2) Commit
the gate layer + refresh `05_praxis-check/CONTEXT.md`. (3) Optional later lever:
targeted full-text passage extraction for OA papers (helps her timing/dosing
questions; paywalled landmarks remain out of reach by guardrail).

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
