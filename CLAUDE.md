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
| The retrieval pipeline at a glance | `kustos-pipeline.png` (the semantic-layer sketch: input, the two model calls in amber, everything between them deterministic; Fetch, Rank, the MeSH Gate, Enrich, Synthesize) |
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
| Project learnings (reference cards) | `learnings/` |
| Quote anchoring (plan, status, A/B gate) | `05_praxis-check/PLAN-quote-anchoring.md` |
| Retrieval relevance (floor, ambiguous abbreviations) | `05_praxis-check/PLAN-retrieval-relevance.md`, `scripts/test_retrieval.py`; replay with `benchmark_praxis.py --replay-retrieval` |
| Claim check (numbers vs evidence the model saw; a screen, not proof) | `scripts/check_claims.py` (+ `test_check_claims.py`, `rebuild_evidence.py`); every CLI run writes `<dossier>.evidence.json` |
| Orchestrator + weekly cron | `scripts/run_weekly.py`, `.github/workflows/weekly.yml` |
| GitHub | https://github.com/jacksoncalling/journal-watch-kustos |

## Current state (Updated 2026-10-16)

**What's working.** Both artifacts ship: Wochenbrief (weekly cron) and
Praxis-Check (CLI plus Replit web UI with brief-first Kurzantwort). On branch
`claim-check-screen` (commits `3528146`, `47b4ac1`; **not merged into main,
not pushed**, so Replit still runs the old pipeline):

- **Evidence per run:** `<dossier>.evidence.json` holds exactly what the model
  saw, the raw prose with quotes, anchors and per-stage timings.
- **Quote anchoring:** the model cites `(PMID x: "verbatim quote")`; code splits
  quotes off before anything is shown; `check_claims.py` checks quote-in-paper
  and number-in-own-quote. A screen, not proof (8 known failures kept in tests).
- **Retrieval relevance:** ambiguous abbreviations expanded (`profile.md`),
  hyphen-tolerant subject gate, 20 is a cap not a target (no padding), up to 3
  marked context guidelines, zero matches = no dossier, under 5 = thin-evidence
  note, planned-query clean-up.
- **Speed:** planner thinking off; 8-question run with synthesis thinking also
  off: about 39 s vs 65 s per dossier, 91 % of quotes verbatim (A/B gate
  passes), no wrong numbers found by hand.
- **Benchmark tooling:** `--only`, `--label`, `--recheck` (free),
  `--replay-retrieval` (no LLM); frozen runs in `05_praxis-check/benchmark-runs/`.
- Retrieval still uses no embeddings, by design (MeSH as controlled vocabulary).

**Known issues.** (1) Setting relevance: papers that name the drug but come
from another clinical setting still pass (pericarditis, PONV, postpartum,
ECMO). (2) Source list still shows all selected papers, not only cited ones.
(3) Gemini still edits about 9 % of quotes; synthesis thinking is still default
in `profile.md` (off only in the test run). (4) Web runs save no evidence
(Replit disk may be ephemeral). (5) "Full text" is a capped excerpt (abstract,
results, conclusion, 8000 chars) with many EBI 500 errors. (6) Checker blind
spots: number words, "v" for versus.

**What's next.** (1) Decide setting check vs Claude Citations (recommended:
setting check, free to test via replay). (2) Merge `claim-check-screen` into
main so Replit gets it; decide synthesis thinking off in `profile.md`.
(3) Clinician answer key for about 5 questions (agreed, not scheduled), then a
claim-support judge calibrated on it.

Full detail: `HANDOFF.md` (top), `05_praxis-check/PLAN-quote-anchoring.md`,
`05_praxis-check/PLAN-retrieval-relevance.md`.

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
