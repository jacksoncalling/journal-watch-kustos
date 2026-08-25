# Brief for building the Kustos web UI (read this first)

This repo is a **finished backend**: a medical-literature pipeline that turns one
clinical question into a cited German dossier (current evidence, what is standard,
where the literature disagrees). The valuable, careful part is already built and
tested. Your job is only the **interface**.

## The one rule

**Build the UI. Call the backend. Do NOT reimplement the dossier or the search
logic.**

The safety of Kustos lives in the Python pipeline, not in the prompt:

- evidence level (Stufe 1/2/3) is computed in code from publication type; the
  model cannot inflate it
- provenance labels (`[VOLLTEXT]`/`[NUR ABSTRACT]`), the DOI/PubMed links, and the
  whole `## Quellen` source list are assembled in code
- citations are validated (a PMID the model invents is caught)
- a fixed footer and a no-dosage-advice boundary are enforced
- no em/en dashes as punctuation

If you write your own call to an LLM instead of calling this pipeline, all of that
is silently gone and the answer is no safer than raw ChatGPT. That is the failure
mode to avoid. Producing the dossier must mean *running the backend code*.

## The backend is already here

`web/app.py` is a working FastAPI reference:

- `GET  /`        serves the chat page (`web/index.html`)
- `POST /praxis`  body `{ "question": "...", "password": "..." }`
  returns `{ "dossier": "<markdown>", "queries": [...], "count": N }`

`/praxis` calls `praxis_check.build_dossier(...)`, the exact pipeline the CLI uses.
Keep that call. You may redesign the page freely (Replit design system welcome),
but the page must POST to `/praxis` and **render the returned `dossier` markdown in
full**, including its `## Quellen` and the footer. Do not summarize or trim it.

## Interaction reference: OpenEvidence

Mobile-first. One prominent question box, submit, then a clean cited answer.

- She is on her phone at work, so design for a narrow screen first.
- A run takes **30 to 90 seconds** (search, enrich ~20 papers, one synthesis
  call). Show a real loading state; do not let it look frozen or time out. The
  reference page rotates status messages while waiting.
- The dossier is structured markdown (`## Evidenzlage`, `## Was ist Standard`,
  `## Wo die Literatur uneins ist`, `## Offene Fragen`, `## Quellen`). Render the
  sources as tappable links.

## Run it

```bash
pip install -r requirements.txt            # pipeline deps
pip install -r web/requirements-app.txt    # fastapi + uvicorn
# .env in the repo root holds GEMINI_API_KEY / ANTHROPIC_API_KEY (already used by
# the pipeline). Add a pilot password:
KUSTOS_APP_PASSWORD=changeme uvicorn app:app --app-dir web --port 8000
```

One service, on Replit. No Supabase, no Vercel, no Render. Dossiers can stay in
the repo/files; a database is not needed for the pilot.

## Auth and scope (pilot)

- A single shared password (`KUSTOS_APP_PASSWORD`) is enough for her plus a couple
  of trusted colleagues. Keep the URL private; do not make it publicly linkable.
- This is a private research pilot, not a product. Keep the footer, do not position
  it as a clinical tool, do not collect patient data.

## Prove you did not break the guardrails

After any build, run the checker on a dossier the app produced:

```bash
python scripts/verify_dossier.py <saved-dossier.md>
```

It asserts: no dashes, one footer, the Quellen and Suchanfrage sections exist, no
evidence labels loose in the prose, and every inline `(PMID …)` is backed by a real
source. Green means the safety layer survived.

Stronger still: run the same question through `python scripts/praxis_check.py
--dry-run` and compare the sources with the app's output. If they match, the app is
truly using the pipeline. If they diverge, it is not.
