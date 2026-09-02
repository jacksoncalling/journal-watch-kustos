---
type: meta
role: checkpoint
---
# Inventory — Pass 1 of the Cartographer run (Kustos / journal-watch)

> This is the honest pile of nouns and the yardstick, not the map. No cards, no
> catalog here. Pass 2 (`cartography.md`) wires these, confirms the ghosts, hunts
> the gaps, and writes `Catalog.md` + `objects/`.

---

## Run header

- **User's question (rules the run).** "Can this app hold its own water in
  production?" Map Kustos so the **next developer** doing a production-readiness
  pass can enter, open one thing, see what it is and what it touches, and stop.
- **Later reader.** A developer who has never seen the repo. Often, in practice, a
  **cold model** picking the codebase up in a fresh session (the repo is already
  built to be walked by one: `CLAUDE.md` is a thin router). Saying the reader is a
  model is the real answer here, not the lesser one.
- **Territory class.** Technical. Shape: a single-maintainer Python **data
  pipeline** (fetch → enrich → rank → synthesize → send), folder-as-database, with
  one LLM judgment call and a thin FastAPI web layer on top. Scale: ~2,660 LOC
  across 11 scripts, one clinician served, one maintainer.
- **Lens mix.**
  1. **Data-flow / pipeline** — *open.* The system's essence is moving and
     transforming literature end to end. Names the stages, the stores, the sinks,
     and the one place judgment enters. This is the right opening lens because the
     spine is literally a five-stage flow.
  2. **Component / dependency (C4)** — *deepen.* Once the flow is named, the
     interesting structure is *what imports what*: the Praxis-Check reuses the five
     weekly transforms by import, and the web layer sits on the Praxis-Check. The
     dependency graph is where "change this without breaking that" lives.
  - Mix of two, capped deliberately. A third lens (Theory of Constraints, on the
    planner bottleneck) was considered and dropped: the reader wants a walkable map,
    not a diagnosis of the bottleneck, and the cartographer refuses to work backward
    from a failure. The bottleneck still appears, as a gradient, not as a verdict.
- **External-depth budget.** Low. The territory is well-understood and the user's
  own gap list is unusually explicit (`HANDOFF.md` "Known gaps & issues"). External
  research is used only to earn the yardstick's two analogues (below), and it
  *deepens*; it does not re-scope. The two analogue deep-dives are flagged
  `UNVERIFIED — research` and are the honest next step, not claimed as done.

---

## Source log

Every noun below cites one of these. All read at commit `85c284e` (branch `main`),
2026-09-02. The territory ships **inside** the repo, so every path resolves for any
reader who clones it.

| # | Source | What it grounds |
|---|---|---|
| S1 | `CLAUDE.md` | Root router, current-state claims, guardrails, run commands |
| S2 | `README.md` | Public story, the five stages, the regulatory boundary |
| S3 | `HANDOFF.md` | Live status, the stage table, the explicit gap list, the palimpsest of dated updates |
| S4 | `scripts/run_weekly.py` | The weekly orchestrator (subprocess chaining + `seen.json` ledger) |
| S5 | `scripts/fetch_europepmc.py` | Fetch stage; Europe PMC query + dedupe |
| S6 | `scripts/enrich.py` | Enrich stage; Unpaywall OA + full-text (ThreadPool, allSettled-shaped) |
| S7 | `scripts/rank.py` (+ `test_rank.py`) | Deterministic evidence level + score; `kanon_keywords` bonus |
| S8 | `scripts/synthesize.py` | The one LLM judgment; code-injected fact line |
| S9 | `scripts/providers.py` | Provider abstraction; Gemini primary (`seed=7`) + Claude fallback |
| S10 | `scripts/send_telegram.py` | Delivery; paper-boundary splitting |
| S11 | `scripts/praxis_check.py` | On-demand orchestrator; the deterministic gate layer; `plan_queries` (temp 0) |
| S12 | `scripts/benchmark_praxis.py` | 7-question cardiac benchmark (the intended regression harness) |
| S13 | `scripts/verify_dossier.py` | Post-hoc guardrail checker on dossier output |
| S14 | `web/app.py` (+ `index.html`, `REPLIT_BRIEF.md`) | FastAPI seam; `POST /praxis` + `/praxis/stream`; password gate |
| S15 | `profil/profile.md` | Config-as-data: topics, journals, provider, Domain-Gate, daily cap |
| S16 | `profil/kanon.md` | Learned memory; consumed by rank |
| S17 | `04_feedback/CONTEXT.md` | The feedback stage's own contract, marked "noch nicht gebaut" |
| S18 | `05_praxis-check/dossier-vertrag.md` | The dossier output contract |
| S19 | `03_brief/CONTEXT.md` | The brief output contract (fed into the synthesis prompt) |
| S20 | `.github/workflows/weekly.yml`, `praxis-check.yml` | The cron / dispatch automation |
| S21 | `05_praxis-check/PLAN-fields-of-inquiry.md`, `PLAN-evidence-quality.md` | Named-but-unbuilt roadmap items |

---

## Reference frame (the yardstick — spent in Pass 2's gap hunt)

The question is "production-readiness for a single-maintainer, LLM-in-the-loop data
pipeline under a regulatory boundary." The yardstick is earned from two grounded
sources, not from a canned checklist.

**(a) The user's own named frameworks** (from Josh's documented learnings, which
are his real production discipline, and from the repo's own stated invariants):

- **Gemini determinism = temperature 0 AND a fixed seed** (learning, 2026). Applied
  live here (`praxis_check.py:205` + `providers.py:76`).
- **`Promise.allSettled` for parallel AI calls**, never `all`. Applied here as the
  "allSettled-shaped" ThreadPool in `enrich_top` (S6).
- **Consume the domain thesaurus, don't build a graph** (learning). Applied: MeSH is
  consumed as the controlled vocabulary; no embeddings, by design.
- **Two-pass extraction / integration** (learning). Mirrored in the pipeline's
  code-vs-judgment split: deterministic retrieval, then one LLM synthesis.
- The repo's own guardrails (S1 §Guardrails): provenance set in code not by the
  model; no dosage advice; no paywall circumvention; no patient data.

**(b) Two comparable analogues — matched to shape and scale**, studied for their
model, their successes, AND their failures. Flagged where the deep study is still
owed:

- **Reproducible scientific-data pipelines (Snakemake / Nextflow family).**
  `UNVERIFIED — research: what does a reproducible-pipeline framework treat as
  non-negotiable that Kustos does not yet — pinned inputs, resumable/idempotent
  re-runs, a provenance manifest per output?` Kustos has the deterministic-scoring
  half; the input side (Europe PMC results drift over time) and per-output
  provenance manifests are the dimensions to test against.
- **LLM-app productionization (eval-gated generation).**
  `UNVERIFIED — research: in a shipped LLM pipeline, what makes an eval a real
  regression gate rather than a one-off benchmark, and how are guardrails enforced
  outside the prompt?` Kustos enforces guardrails in code (strong) and has a
  benchmark (S12) but, by its own account, it "is not yet a clean regression gate."

**Dimensions a production-ready version of this territory should carry** (read off
the two sources above, to be laid against the map in Pass 2):

1. Determinism / reproducibility of every non-judgment step.
2. A regression gate that actually gates (an eval wired into CI, not run by hand).
3. Provenance and guardrails enforced in code, not by the model.
4. Idempotent, failure-isolated runs (one stage fails → the next never runs).
5. Secrets and patient-data hygiene.
6. Test coverage across the parsing/transform seams, not just one stage.
7. Observability (can a cold operator see why a run produced what it did?).
8. Bus-factor: doc-to-code fidelity, so the next reader is not misled.
9. **A live user.** The ultimate production test: does it actually run for someone real?

---

## Noun inventory (provisional marks, from the source alone)

Marks are **provisional** — a source reading, not the Pass-2 verdict. Type is the
closed set in `reference/card-types.md`. `hub` is the catalog shelf, not an edge.

### hub: pipeline (the five transforms + the provider seam)

| Noun | Type | Mark | Source | Note |
|---|---|---|---|---|
| Fetch (Europe PMC) | Capability | live | S5 | Boolean Europe PMC query, dedupe → `candidates.json` |
| Enrich (OA + full text) | Capability | live | S6 | Unpaywall + EPMC full text; parallel, allSettled-shaped |
| Rank (evidence + score) | Capability | live | S7 | Pure code; evidence level from pub-type; `kanon` bonus wired |
| Synthesize (the one LLM call) | Capability | live | S8 | Judgment used exactly once; fact line injected in code |
| Send (Telegram) | Capability | live | S10 | Paper-boundary splitting; no 429/retry (noted) |
| Provider abstraction | Capability | live | S9 | Gemini `seed=7` primary, Claude Sonnet fallback |

### hub: orchestration

| Noun | Type | Mark | Source | Note |
|---|---|---|---|---|
| Weekly orchestrator | Capability | live | S4 | Chains 5 stages as subprocesses; writes `seen.json` after confirmed send |
| Praxis-Check orchestrator | Capability | live | S11 | Reuses the 5 transforms by import; adds the gate layer; all-time search |
| Web seam (FastAPI) | Capability | live | S14 | `POST /praxis` + SSE `/praxis/stream`; password gate, fails closed |
| Weekly cron (GitHub Action) | Instrument | pending | S20 | Built; auto-detects live vs dry; not yet exercised on GitHub per S3 |

### hub: retrieval-layer (the deterministic semantic layer)

| Noun | Type | Mark | Source | Note |
|---|---|---|---|---|
| Deterministic gate layer | Capability | live | S11 | Subject-actor gate, retraction gate, MeSH negative gate, cardiac-MeSH bonus |
| Query planner (LLM → EPMC query) | Capability | live | S11 | Pinned: temperature 0 + provider seed 7. The one nondeterministic seam, now pinned |
| MeSH thesaurus | Shared Resource | live | S1, S11 | Consumed as controlled vocabulary; not built. External, professionally maintained |
| Abbrev → MeSH-term expansion | Capability | **ghost-candidate** | S1(next), S15 | Specced in "what's next"; verify in Pass 2 whether `profile.md` Domain-Gate actually expands abbreviations into queries, or only gates |

### hub: memory (folder-as-database)

| Noun | Type | Mark | Source | Note |
|---|---|---|---|---|
| Profile (config-as-data) | Shared Resource | live | S15 | Topics, journals, provider, Domain-Gate, `max_dossiers_per_day`. Demo "Dr. Demo" |
| Kanon (learned memory) | Shared Resource | live | S16 | Read by rank (`kanon_keywords`); grows only by confirmed lines |
| Run ledgers (`seen`/`candidates`/`selected`/`usage`.json) | Shared Resource | live | S4, S11 | Gitignored run state; `seen.json` = cross-week dedup; `usage.json` = cost cap |
| `.env` secrets | Shared Resource | live | S1 | Gitignored; `GEMINI/ANTHROPIC/TELEGRAM` keys |

### hub: contracts (formal binding/enabling devices) + boundary

| Noun | Type | Mark | Source | Note |
|---|---|---|---|---|
| The guardrails | Instrument | live | S1, S2 | No dosage advice, no paywall circumvention, no patient data, provenance-in-code, no em-dash. Enforced in code |
| Dossier-Vertrag | Instrument | live | S18 | Binds Praxis-Check output shape (Kernbefund-first, evidence-attributed, tangential exclusion) |
| Brief contract | Instrument | live | S19 | Fed into the synthesis system prompt |
| Citations contract (WP-A) | Instrument | live | S3 | `citation_view()` JSON per-paper; `POST /praxis` returns `citations[]` |
| Regulatory boundary (MDR / AI Act / MDCG 2019-11) | Jurisdiction | live | S2 | The envelope that decides intended purpose. Kustos sits deliberately below the device threshold |
| Apache License 2.0 | Instrument | live | `LICENSE` | Public method repo |

### hub: verification (the checkers)

| Noun | Type | Mark | Source | Note |
|---|---|---|---|---|
| Cardiac benchmark | Capability | leftover | S12 | Runs, tuned 7Q; by its own account "not yet a clean regression gate" — runnable but not gating |
| `test_rank` | Capability | live | S7 | 12/12 evidence-mapping tests pass. The only committed unit tests |
| `verify_dossier` | Capability | live | S13 | Post-hoc guardrail checker on dossier output (7 checks) |

### hub: surface (external actors)

| Noun | Type | Mark | Source | Note |
|---|---|---|---|---|
| The clinician (served) | Actor | **ghost / pending** | S2, S3 | Only "Dr. Demo" (a fiction) is wired. The *real* clinician is step 8, not yet instantiated |
| The maintainer (Josh) | Actor | live | S1 | Holds every capability; the single point of continuity and the doc-drift source |
| Europe PMC | Actor / Shared Resource | live | S5 | The literature corpus; the retrieval source of truth |
| Unpaywall | Actor | live | S6 | OA-link service |
| Gemini / Anthropic | Actor | live | S9 | LLM providers behind `providers` |
| Telegram | Actor | live | S10 | The delivery channel |
| Replit | Actor | live | S14 | Hosts the web layer; the "team member" that wrote `web/` |

---

## Ghost-candidates (what Pass 2 must confirm on evidence)

1. **`04_feedback` automated writer** — a folder + a contract (S17) that says of
   itself "noch nicht gebaut." No code references it. The live substitute is a
   human loop (she texts Josh, Josh hand-edits `kanon.md`). Named, unwired: the
   textbook ghost. *Note the split:* the kanon → rank *output* edge is LIVE (S7);
   only the automated *input* writer is the ghost.
2. **The real clinician / private instantiation** — the product's actual reason to
   exist (S3, step 8). The live product has a fiction for a user. A named-but-absent
   holder of the value.
3. **RSS fetch (`fetch_rss.py`)** — named as a second fetch source (S3), deferred,
   no file. Named, unwired.
4. **Per-user quota** — named (S3); the built cap is global (S11). Named, unwired.
5. **Abbrev → MeSH-term expansion layer** — see the retrieval-layer table. Confirm
   in Pass 2 whether it exists in `profile.md` or is purely roadmap.
6. **Clean regression gate** — the benchmark (S12) exists but does not gate CI.
   Confirm whether anything runs it automatically, or only by hand.

## Candidate evaluative layer (relief — to detect/voice in Pass 2, not invent)

- **Tension: deterministic machinery vs the single LLM seam.** Everything is
  deterministic code *except* one judgment call; the design's honesty rests on
  keeping that seam tiny and pinned. Both sides live now.
- **Tension: bibliographic library vs clinical decision support.** The product's
  value to the clinician grows the closer it moves to "what should I do for this
  patient," but that is the exact MDR line that expelled OpenEvidence from the EU
  (S2). The guardrails hold it on the low-value, legal side on purpose.
- **Tension: public method repo (Dr. Demo) vs the real private instantiation.**
  "Build out loud" vs serve a real clinician's sensitive real topics.
- **Gradient: documentation drift.** Direction: session notes accrete faster than
  they are reconciled. Cost: a cold reader trusts a stale line. Threshold already
  crossed in ≥3 places (S3 says "04_feedback missing" and "not a git repo"; S1 says
  planner nondeterminism is the ceiling — all three are false against the code).
- **Gradient: presentation over retrieval.** Direction: the cheap wins are
  surfacing data Kustos already computes and hides (inline citations, study-type
  badges), not new retrieval (S3, 08-30). Threshold: the guardrail that
  `stufe`/`study_type` are never recomputed client-side.

---

*Pass 1 complete. The pile is honest and every noun cites a source. Proceed to
`cartography.md`: wire the typed movements, apply the degree tripwire to confirm the
six ghost-candidates, run the two gap hunts, and write `Catalog.md` + `objects/`.*
