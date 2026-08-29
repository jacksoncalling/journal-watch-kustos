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
  returns `{ "dossier": "<markdown>", "queries": [...], "count": N, "citations": [...] }`

`/praxis` calls `praxis_check.build_dossier(...)`, the exact pipeline the CLI uses.
Keep that call. You may redesign the page freely (Replit design system welcome),
but the page must POST to `/praxis` and **render the returned `dossier` markdown in
full**, including its `## Quellen` and the footer. Do not summarize or trim it.

### `citations`: the payload for tappable references

`citations` is one object per paper in the dossier's source list, in the same
order as `## Quellen`, so it can back tappable inline citations or a reference
list without any extra parsing on your side. Every field is set by the Python
pipeline (evidence tier, study type, provenance), never by the model, so
**render what is here, do not compute your own Stufe or study-type label**.

Example object:

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
  "snippet": "first ~240 chars of abstract, for a tap-to-preview card"
}
```

- `stufe` is 1 (strongest) to 3 (weakest); `study_type` is the plain-language
  name for the same tier (`"Meta-Analyse"`, `"Systematic Review"`, `"RCT"`,
  `"Beobachtungsstudie"`, `"Leitlinie"`, `"Review"`, `"Case Report"`,
  `"Editorial"`, or the fallback `"Studie"`). They are derived from the same
  publication-type data, so they never disagree.
- `doi` and `oa_url` can be `null`; only render a link when the field is set.
  `full_text` is `true` only when the pipeline actually pulled a full-text
  excerpt (PMC open access), not just when `oa_url` is present.
- The dossier markdown still carries inline `(PMID 12345678)` anchors; match
  those against `citations[].pmid` to build a tap target. Do not invent a
  citation for a PMID that is not in this array.

## Streaming: `POST /praxis/stream` (Work package B, F1)

The 90 second wait cannot be tuned down (it is a deep 200-paper search + per-paper
enrich + one real synthesis call, and shortening any of those is the freshness and
provenance we are selling, see PLAN-fields-of-inquiry.md). So instead of tuning the
wait, this endpoint makes it **feel** fast: it emits progress as each pipeline stage
lands, using the exact same guarded pipeline as `/praxis` (same `build_dossier`
internals, so nothing in the safety layer is duplicated or skipped).

Request body is identical to `/praxis`: `{ "question": "...", "password": "..." }`.
Auth and length validation happen synchronously before the stream opens, so a bad
password or too-short question still returns a normal `401`/`400`/`503`/`429`, not
an SSE error. Once the stream has started, a real HTTP status is no longer possible
(the response already committed to `200` and `text/event-stream`), so a mid-run
failure (the rare daily-cap race, no candidates found, provider error) arrives as
an `error` event carrying the status it would have been.

Response is `text/event-stream`. Each event is one SSE block:

```
event: <name>
data: <json>

```

Events, in order:

1. **`searching`** as soon as the search query is resolved (LLM-planned or
   explicit): `{ "queries": ["..."] }`
2. **`found`** once ranking + enrich (OA links, full-text) finish, same
   `citations[]` shape as `/praxis`: `{ "count": N, "citations": [ {A2 objects} ] }`
3. **`synthesis`** once the one synthesis call returns. This is the raw model
   prose only (no `## Quellen`, no `Verwendete Suchanfrage`, no footer, those are
   code-appended after): `{ "text": "..." }`. **Not token-by-token**: the
   provider call blocks on `get_final_message()` so it can check the Anthropic
   `refusal` stop_reason and try the fallback provider before any text is
   trusted, so this arrives as one chunk. Show it the moment it lands rather
   than waiting for `done`.
4. **`done`** the finished dossier, same shape as the whole `/praxis` response
   so you can treat it as the authoritative final state:
   `{ "dossier": "...", "queries": [...], "count": N, "citations": [...] }`

Error path, instead of `4`:

- **`error`**: `{ "status": 401 | 422 | 429 | 500, "detail": "..." }`. Render
  `detail` the same way you would a failed `/praxis` call; `status` mirrors what
  the non-streaming endpoint would have returned for the same failure.

Recommended render: show the queries the moment `searching` arrives, render the
citation cards from `found` (same tap-to-preview cards as the non-streaming path,
A4), then swap in the `synthesis` prose, then replace everything with `done`'s
`dossier` once it lands (it is byte-identical prose plus the code-appended
Quellen/Suchanfrage/footer). Keep the existing `/praxis` call as a fallback if a
host's proxy does not support SSE cleanly; both hit the identical pipeline.

## Interaction reference: OpenEvidence

The visual target is `web/journey-sketch.html` (open it in a browser): the user
journey and mobile wireframes, grounded in the user interview. Match that flow.

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
pip install -r requirements.txt            # pipeline deps (anthropic, google-genai)
pip install -r web/requirements-app.txt    # fastapi + uvicorn
# locally, .env in the repo root holds the keys; add a pilot password:
KUSTOS_APP_PASSWORD=changeme uvicorn app:app --app-dir web --port 8000
```

One service, on Replit. No Supabase, no Vercel, no Render. Dossiers can stay in
the repo/files; a database is not needed for the pilot.

## Deploying on Replit (the setup steps)

The `.env` is gitignored and is NOT in the repo, so Replit has no keys until you
add them. Set these as **Replit Secrets**:

- `GEMINI_API_KEY`      required (primary: synthesis and query planning)
- `ANTHROPIC_API_KEY`   optional (fallback provider)
- `KUSTOS_APP_PASSWORD` required, or `/praxis` returns 503 (fails closed by design)

Telegram secrets are NOT needed here; they belong to the weekly brief, not this app.

Install **both** requirements files (above). Run command for hosting (bind all
interfaces and use Replit's port):

```bash
uvicorn app:app --app-dir web --host 0.0.0.0 --port $PORT
```

**Request timeout matters.** One dossier takes 30 to ~110 seconds. Pick a
deployment that allows a request that long: a **Reserved VM** is safest. On
Autoscale, raise the request timeout above ~120s, or the proxy will cut the
request mid-run and the page will look broken. This is the single most likely
deploy-time surprise.

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
