# Plan: Fields of Inquiry (post OpenEvidence/Heidi head-to-head)

Companion to the visual map (`05_praxis-check/fields-of-inquiry-map.html`).
Derived from a clinician running her own Aortenbogen case question through
OpenEvidence, Heidi, and the Kustos Praxis-Check (2026-08-30).

This is a build plan, split by **who does what**, because the frontend lives on
Replit and the backend lives here. Read the "Division of labour" section before
picking up any task. Nothing here is built yet.

## The one-line read

What she loved (inline tappable citations, study type at a glance) is mostly data
Kustos **already computes and hides**. What she worried about (missing American
journals) is **false**: `SRC:MED` is MEDLINE, the US-run index, and her dossier
already cited American Heart Journal, Anesthesiology, Anesthesia & Analgesia. So
the cheap, high-ROI work is **presentation**, and the one genuine research field
is corpus source-type (guidelines/currency), not nationality.

## Division of labour (read this first)

Three lanes. Keep them from stepping on each other.

| Lane | Who | Where | What |
|---|---|---|---|
| **Pipeline / backend** | Sonnet in this repo | `scripts/`, `profil/` | Compute the citation payload, study-type labels, streaming hooks, corpus passes. Guardrails live here by construction. |
| **API seam** | Sonnet in this repo | `web/app.py` | The JSON contract the frontend consumes. This is the handshake. Define it once, freeze it, document it in `web/REPLIT_BRIEF.md`. |
| **Frontend / rendering** | Replit agents | `web/index.html` + Replit UI | Turn the contract into tappable citations, study-type badges, streamed text. **They should not touch `scripts/` or reimplement any guardrail.** |

**Coordination rule:** the frontend can only render what the API sends. So the
API-seam task (F2/F3 contract below) is the **critical path** and must land and
be documented before the Replit agents start, or they will build against a shape
that does not exist. When the contract changes, update `web/REPLIT_BRIEF.md` in
the same commit.

---

## Work package A — Citations contract (enables F2 + F3). CRITICAL PATH.

Today `web/app.py` returns `{dossier, queries, count}` and **throws away
`result.selected`**, which already carries everything the frontend needs. This
package exposes it. No pipeline logic changes, only what we serialize.

### A1. Backend: study-type label (Sonnet, `scripts/rank.py`)
- Add `study_type_label(pub_types: list[str]) -> str` next to `evidence_level`.
  Same input, deterministic, human-facing. Map to a short set she can rank in her
  head: `"Meta-Analyse"`, `"Systematic Review"`, `"RCT"`, `"Beobachtungsstudie"`,
  `"Leitlinie"`, `"Review"`, `"Case Report"`, `"Editorial"`, fallback `"Studie"`.
- Reuse the existing pub-type mapping that already drives Stufe, so label and
  Stufe never disagree (Stufe is the tier, label is the plain name).
- Test: extend `scripts/test_rank.py` with a label case per pub-type bucket.

### A2. Backend: a serializable citation view (Sonnet, `scripts/praxis_check.py`)
- Add `citation_view(selected: list[dict]) -> list[dict]`. One object per paper,
  drawn from fields that already exist on each `selected` item:
  ```json
  {
    "pmid": "35786218",
    "title": "Does methylprednisolone provide protective effect ...",
    "journal": "Perfusion",
    "year": 2022,
    "study_type": "Beobachtungsstudie",
    "stufe": 3,
    "doi": "10.1177/02676591221113650",
    "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/35786218",
    "oa_url": null,
    "full_text": false,
    "snippet": "first ~240 chars of abstract, for the tap-to-preview card"
  }
  ```
- `stufe`, `study_type`, `pubmed_url`, `oa_url`, `full_text` all come from data
  the pipeline already set (`rank.evidence_level`, A1, `enrich_top`). `snippet` is
  a truncation of the existing `abstract`. **Do not fetch anything new.**
- Keep provenance honest: `stufe`/`study_type`/`full_text` are set here in code,
  never by the model. Same guarantee as `assemble_quellen`.

### A3. API: return the array (Sonnet, `web/app.py`)
- `POST /praxis` response becomes:
  ```json
  { "dossier": "...markdown...", "queries": [...], "count": 12,
    "citations": [ ... A2 objects ... ] }
  ```
- Keep `dossier` markdown unchanged (Telegram and the CLI still consume it; the
  inline `(PMID …)` anchors stay). `citations` is additive, so nothing breaks.
- Document the new field in `web/REPLIT_BRIEF.md` with the example above.

### A4. Frontend: tappable citations + badges (Replit agents, `web/index.html`)
- Parse the rendered dossier for inline `(PMID 12345678)` / `(PMID x, y)` tokens.
  Replace each with a tap target linked to the matching `citations[]` entry by
  `pmid`.
- On tap: a small card showing `study_type` badge, `journal`, `year`, Stufe, the
  `snippet`, and outbound links (`pubmed_url`, `oa_url` when present). This is the
  "reference is right there, and I can see what kind of study it is" behaviour.
- Badge styling mirrors the visual map chips (RCT / SR / Review). Colour by Stufe
  so tier reads at a glance.
- **Frontend never invents a Stufe or label. Render only what `citations[]` says.**

**Acceptance for A:** her Aortenbogen dossier renders with every inline PMID
tappable, each opening a card with the correct study type and links, no PMID
un-mapped, no Stufe/label computed client-side.

---

## Work package B — Streaming (F1). Perceived-latency win.

The 90s is inherent to live retrieval and cannot be tuned to 10s. So make it
**feel** fast instead of racing a cached product.

- **B1 (Sonnet, `web/app.py`):** add a streaming endpoint (SSE or chunked) that
  emits, in order: (1) "searching" + the resolved queries, (2) "found N papers"
  + the `citations[]` array, (3) the synthesis text as it arrives, (4) done. The
  synthesis LLM call already streams; surface it. Keep the existing non-streaming
  `POST /praxis` for the CLI/Telegram path.
- **B2 (Sonnet, `scripts/praxis_check.py`):** parallelize `enrich_top`'s per-paper
  round-trips (they are independent network calls; today they are serial). Use
  `Promise.allSettled`-equivalent semantics (one failure must not sink the batch),
  matching the house rule for parallel external calls.
- **B3 (Replit agents, `web/index.html`):** progressive render. Show the query +
  citation list the moment they arrive, then stream the prose. The user watches
  progress instead of a 90s spinner.
- **Guardrail:** do not drop the deep pool or the enrich step to save time. That
  is the freshness/provenance we are selling. Speed comes from parallelism and
  streaming, not from retrieving less.

**Acceptance for B:** first meaningful paint (queries + paper count) under ~5s;
prose streams; total wall-clock unchanged but the wait no longer reads as dead.

---

## Work package C — Corpus source-type (F4). The one real research field.

Do this **after** the cited-only-Quellen fix in `PLAN-evidence-quality.md` #2,
because widening retrieval widens leaks, and cited-only is the backstop.

- **C1:** a guidelines-aware retrieval pass. Society statements answer "was ist
  Standard" better than primary trials. Options to investigate: a pub-type /
  MeSH filter for `Guideline`/`Practice Guideline`, or a dedicated query arm.
- **C2:** currency signal. Citation-sort buries this year's guideline under a 2010
  landmark. Investigate a recency-aware second sort arm or a small recency bonus
  that does not drown the landmark trials the current sort is designed to surface.
- **C3:** surface ongoing/registered trials (the Medal trial is exactly what she
  wanted flagged) when a paper's pub-type marks it as a protocol/design paper.
- **Risk:** leaks and off-topic breadth. Gate every addition through the existing
  MeSH domain-gate and the benchmark (`scripts/benchmark_praxis.py`) before
  shipping. This is research, not a rendering change; expect iteration.

## Work package D — Format-fit (F5). Product, later.

Already half-scoped in `PLAN-evidence-quality.md` #3. Detect lookup-shaped
questions (dose / target / "what is X") and return a terser, more scannable form;
keep the four-section evidence map for controversy-shaped questions. Bigger
change, lowest urgency, do after A/B land and the evidence-quality fixes settle.

## F6 is a standing constraint, not a task

Every package above keeps Kustos's identity: controversy-first, full provenance,
her journals, no dose-as-advice. We copy OpenEvidence's **presentation**, never
its willingness to hand back a bare mg/kg number. If a proposed change softens a
guardrail to look more like OE, that is the signal to stop and ask Josh.

---

## Sequence

1. **Package A** (citations contract) + **Package B** (streaming). Cheap, high
   ROI, mostly surfacing existing data. A3 is the critical path for the Replit
   agents, so land and document it first.
2. **`PLAN-evidence-quality.md`** fixes (phantom PMIDs, cited-only Quellen,
   Kernbefund weighting). Independent, already planned.
3. **Package C** (corpus) alongside **Package D** (format). Real research; gate on
   the benchmark.

## What NOT to do

- Do not add "American journals." We already have MEDLINE. F4 is source-type.
- Do not race OpenEvidence to 10s by retrieving less. Stream instead.
- Do not let the frontend compute Stufe, study type, or provenance. It renders
  the `citations[]` the backend sends; that keeps the guardrails in one place.
- Do not rebuild the pipeline. A2/A3 are additive serialization of `selected`,
  not new retrieval or synthesis.
