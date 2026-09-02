---
type: meta
role: front-door
---
# Catalog — Kustos (journal-watch)

> The front door. It points; it stores almost nothing. Ask one question, open one
> card, stop. Never load the whole `objects/` folder. Marks: **live** (wired now),
> **pending** (sourced, on track), **leftover** (was live, honest residue),
> **ghost** (named, no wiring). The map is a prototype pointing at the code; if a
> card and the file disagree, **the file wins**.

**Reader:** a developer (often a cold model) doing a production-readiness pass on a
single-maintainer Python literature pipeline. **What it is really about:** see
[[North Star]]. **How the pile was built:** see [[Inventory]] (Pass 1).

---

## If you have one question, start here

- *"What actually runs each week?"* → [[Weekly Orchestrator]], then the five stages.
- *"Where could it fabricate?"* → [[Synthesize]] (the one LLM judgment) and [[The Guardrails]].
- *"Is retrieval reproducible?"* → [[Query Planner]] and [[Determinism vs the LLM Seam]].
- *"Who does this serve?"* → [[The Clinician]] (the load-bearing ghost).
- *"Why is it shaped this way?"* → [[No Embeddings]], [[Folder is the Database]].
- *"Is it legal?"* → [[Regulatory Boundary]].
- *"Can I trust the docs?"* → [[Documentation Drift]] (no; trust the code).

---

## The pipeline (the five transforms + the provider seam)

The weekly spine: fetch what is new, annotate it, score it in code, write it once
with judgment, deliver it.

- [[Fetch]] · Capability · live — Europe PMC query + dedupe.
- [[Enrich]] · Capability · live — OA links + full text, parallel, allSettled-shaped.
- [[Rank]] · Capability · live — evidence level + score, pure code, reads Kanon.
- [[Synthesize]] · Capability · live — **the one LLM call**; fact line injected in code.
- [[Send]] · Capability · live — Telegram, split at paper boundaries.
- [[Provider Abstraction]] · Capability · live — Gemini (seed 7) + Claude fallback.

## Orchestration (how the transforms are composed)

- [[Weekly Orchestrator]] · Capability · live — chains the five as subprocesses.
- [[Praxis-Check]] · Capability · live — reuses the five by import; adds the gate layer.
- [[Web Seam]] · Capability · live — the FastAPI phone surface (built by Replit).
- [[Weekly Cron]] · Instrument · **pending** — the GitHub Action, not yet run on GitHub.

## The retrieval layer (deterministic semantics, no vectors)

- [[Gate Layer]] · Capability · live — subject / retraction / MeSH gates + cardiac bonus.
- [[Query Planner]] · Capability · live — the one LLM seam, pinned (temp 0 + seed 7).
- [[MeSH Thesaurus]] · Shared Resource · live — the consumed controlled vocabulary.
- [[Abbrev-MeSH Expansion]] · **ghost** — specced next; would strengthen both above.

## Memory & sources (the folder is the database)

- [[Profile]] · Shared Resource · live — config-as-data (topics, journals, gates, cap).
- [[Kanon]] · Shared Resource · live — learned taste; read by Rank, written by hand.
- [[Run Ledgers]] · Shared Resource · live — seen/candidates/usage.json, disposable state.
- [[Europe PMC]] · Shared Resource · live — the external literature corpus (drifts).

## Contracts & boundary (what binds behaviour)

- [[The Guardrails]] · Instrument · live — no-dosage / no-paywall / provenance-in-code.
- [[Dossier-Vertrag]] · Instrument · live — Praxis-Check output contract.
- [[Brief Contract]] · Instrument · live — weekly Wochenbrief contract.
- [[Regulatory Boundary]] · Jurisdiction · live — MDR / AI Act; sits below the device line.

## Decisions (why it is shaped this way)

- [[No Embeddings]] · Decision · live — boolean + deterministic scoring + MeSH, no vectors.
- [[Folder is the Database]] · Decision · live — files, no server, no DB.

## Verification (the checkers)

- [[Cardiac Benchmark]] · Capability · **leftover** — a real eval that does not yet gate CI.
- [[verify_dossier]] · Capability · live — the offline guardrail checker.

## People & parties

- [[The Maintainer]] · Actor · live — Josh; holds everything (bus-factor of one).
- [[Replit]] · Actor · live — built and hosts the web layer (the second pair of hands).
- [[Telegram]] · Actor · live — the weekly delivery channel.
- [[The Clinician]] · Actor · **ghost** — only "Dr. Demo" is wired; the real user is unbuilt.

## Ghosts (named, no wiring — tripwires, not deletions)

- [[The Clinician]] — the served user; a fiction stands in. **Most load-bearing absence.**
- [[Feedback Stage]] — `04_feedback`, "noch nicht gebaut"; a human does its job.
- [[Abbrev-MeSH Expansion]] — the controlled-vocabulary layer named as next.
- [[RSS Fetch]] — a second source, deferred, no file.
- [[Per-User Quota]] — per-user fairness; cap is global, no user identity yet.

## The relief (tensions & gradients — the terrain the nouns sit in)

- [[Determinism vs the LLM Seam]] · Tension — deterministic everywhere except two LLM seams.
- [[Library vs Decision Support]] · Tension — usefulness pulls toward the MDR device line.
- [[Demo vs Real Instantiation]] · Tension — public fiction vs a real private user.
- [[Documentation Drift]] · Gradient — notes drift faster than one maintainer reconciles.
- [[Presentation over Retrieval]] · Gradient — the cheap wins are surfacing hidden data.
