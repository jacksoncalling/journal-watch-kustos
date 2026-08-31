# Replit prompts for the Kustos web app

Copy-paste prompts for Replit's Agent to host this repo's web app. Read
`web/REPLIT_BRIEF.md` first; it is the source of truth for the API contract
(including the streaming event contract). These prompts drive the sequence and
keep the Agent from rebuilding the pipeline.

**The one rule** (repeat it to the Agent whenever it drifts): build the UI and
host it, call the existing Python pipeline through the FastAPI endpoints, and
never reimplement the dossier, the search, the gates, or the guardrails.

## Facts to have ready

- **Secrets** (you set these in Replit's Secrets tab, not the Agent):
  - `GEMINI_API_KEY` required
  - `KUSTOS_APP_PASSWORD` required (or the app fails closed with 503)
  - `ANTHROPIC_API_KEY` optional fallback. Telegram secrets are NOT needed here.
- **Run command:** `uvicorn app:app --app-dir web --host 0.0.0.0 --port $PORT`
- **Already built in `web/app.py`** (do not rebuild these):
  - `GET  /`             serves the page
  - `POST /praxis`        returns `{ dossier, queries, count, citations }` (blocking, 30 to 90 s)
  - `POST /praxis/stream` Server-Sent Events (`searching`, `found`, `synthesis`, `done`, `error`) for a live-progress wait
  - a daily question cap returns `429`
- **The UI** (`web/index.html`) is already built, matches `web/journey-sketch.html`,
  and currently uses the blocking `/praxis`.

## 0. Import

In Replit: Create Repl, Import from GitHub,
`https://github.com/jacksoncalling/journal-watch-kustos`.

## 1. Get it running

```text
This Repl is imported from a GitHub repo that is ALREADY a finished Python backend with a working FastAPI web app in web/. Open and read web/REPLIT_BRIEF.md first and follow it exactly.

Your only job right now is to get the existing app running. Do NOT reimplement the dossier, the search, the gates, or any Python logic, and do NOT add a database, Supabase, or a second service.

Steps:
1. Install both requirement files: pip install -r requirements.txt AND pip install -r web/requirements-app.txt
2. Set the run command to: uvicorn app:app --app-dir web --host 0.0.0.0 --port $PORT
3. The app reads these Secrets (I add them in the Secrets tab): GEMINI_API_KEY, KUSTOS_APP_PASSWORD, optionally ANTHROPIC_API_KEY. Never hardcode them.
4. Start it, confirm GET / serves the page and POST /praxis works, and tell me the URL to open.

Do not change anything under scripts/ or 05_praxis-check/, or the endpoints in web/app.py. If something fails, fix the config, not the pipeline.
```

## 2. Deploy (the long-request timeout is the crux)

```text
Deploy this app. One /praxis request runs 30 to 110 seconds because it does a live literature search plus a synthesis, so this is the make-or-break setting: choose a deployment that allows a request that long. Use a Reserved VM, or if you use Autoscale, raise the request timeout above 120 seconds and do not buffer responses (the app already sends X-Accel-Buffering: no). Bind to 0.0.0.0 and use $PORT. Confirm the deployment has GEMINI_API_KEY and KUSTOS_APP_PASSWORD set as Secrets. Keep it to this ONE service, no database. After deploy, load the page and run one real question end to end to confirm it completes without a proxy timeout.
```

## 3. Optional: use the streaming endpoint for a robust wait

```text
Optional improvement. The app already has a streaming endpoint, POST /praxis/stream, that emits Server-Sent Events (searching, found, synthesis, done, error) so the wait shows real progress and survives proxy timeouts better than a silent 90-second POST. If the blocking /praxis times out on this deployment, switch web/index.html to consume /praxis/stream instead. The event contract is in web/REPLIT_BRIEF.md.

Constraints: only touch web/index.html. Keep rendering the FULL dossier markdown from the done event, including the ## Quellen list and the footer. Do not add your own AI call. Do not touch app.py or anything under scripts/.
```

## 4. Prove the guardrails survived

```text
Ask the deployed app a real question (password from Secrets), save the returned dossier markdown to a file called check.md, and run: python scripts/verify_dossier.py check.md

It must print "ALL GUARDRAILS HELD." If any line says FAIL, the app is not returning what the pipeline produced; fix the wiring, not verify_dossier.py. Note: the app has a daily question cap and returns 429 once it is hit; that is expected, not a bug.
```

## Drift guard (paste any time the Agent starts rewriting things)

```text
Reminder: do not reimplement or bypass the Python pipeline. The dossier must come from the existing FastAPI endpoints (/praxis or /praxis/stream), which call praxis_check.build_dossier. Your work is the UI and the hosting only. Everything under scripts/ and 05_praxis-check/, and the endpoints in web/app.py, is off limits.
```

Two notes from experience: get step 1 to a working baseline before any UI change,
so if something breaks you know it was the change. And if the Agent proposes
rewriting the backend in Node or "simplifying" the search, that is the exact
failure `REPLIT_BRIEF.md` warns about; send the drift guard and point it back to
the brief.
