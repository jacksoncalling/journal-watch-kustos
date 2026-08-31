#!/usr/bin/env python3
"""Kustos web app: a thin OpenEvidence-style skin over the Praxis-Check pipeline.

This is the REFERENCE backend, and its whole job is small: take a question from
the browser, call `praxis_check.build_dossier` (the exact guarded pipeline the
CLI uses), and return the dossier markdown. It does NOT reimplement search,
synthesis, evidence levels, provenance, or any guardrail. Those all live in the
pipeline and run by construction because producing the dossier IS running that
code. See web/REPLIT_BRIEF.md for the one rule a UI builder must not break.

Run locally (from the repo root):
  pip install -r web/requirements-app.txt
  # keys come from the repo .env, same loader the CLI uses; set a pilot password:
  KUSTOS_APP_PASSWORD=changeme uvicorn app:app --app-dir web --port 8000
  open http://localhost:8000

API:
  GET  /         -> the chat page (web/index.html)
  POST /praxis   -> { question, password }
                 -> { dossier, queries, count, citations }
  POST /praxis/stream -> { question, password }
                 -> Server-Sent Events (searching, found, synthesis, done | error)
                    See web/REPLIT_BRIEF.md for the event contract.
"""
from __future__ import annotations

import hmac
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
WEB = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))   # so `import praxis_check` resolves
import praxis_check as pc  # noqa: E402

MIN_QUESTION_CHARS = 10
MAX_QUESTION_CHARS = 2000   # cap prompt size / cost on a shared, hosted app

app = FastAPI(title="Kustos Praxis-Check")


class Ask(BaseModel):
    question: str
    password: str | None = None


def _required_password() -> str | None:
    """Pilot-grade shared password. Lives in the environment or the repo .env
    (the same loader the pipeline uses for API keys), so one .env holds it all."""
    return (os.environ.get("KUSTOS_APP_PASSWORD")
            or pc.synth.load_env("KUSTOS_APP_PASSWORD"))


def _allow_no_auth() -> bool:
    """Running with no password is allowed ONLY when explicitly opted in, so a
    hosted deploy that forgot to set the password fails closed instead of
    silently serving a public medical app."""
    return os.environ.get("KUSTOS_ALLOW_NO_AUTH") == "1"


if not _required_password() and not _allow_no_auth():
    print("WARNING: KUSTOS_APP_PASSWORD is not set. /praxis will refuse requests. "
          "Set the password, or KUSTOS_ALLOW_NO_AUTH=1 for a local-only test.",
          file=sys.stderr)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


def _authorize_and_validate(ask: Ask) -> str:
    """Password check + length validation shared by both `/praxis` and
    `/praxis/stream`, so the two entry points enforce exactly the same gate.
    Returns the stripped question, or raises the same HTTPException either
    endpoint would raise (real HTTP status, since this runs before any
    response, streaming or not, has started)."""
    needed = _required_password()
    if not needed:
        if not _allow_no_auth():
            raise HTTPException(status_code=503,
                                detail="App nicht konfiguriert (kein Passwort gesetzt).")
    elif not hmac.compare_digest(ask.password or "", needed):
        raise HTTPException(status_code=401, detail="Falsches Passwort.")

    question = (ask.question or "").strip()
    if len(question) < MIN_QUESTION_CHARS:
        raise HTTPException(status_code=400,
                            detail="Bitte eine ausführlichere Frage stellen.")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(status_code=400,
                            detail="Frage ist zu lang (max. 2000 Zeichen).")
    return question


@app.post("/praxis")
def praxis(ask: Ask) -> dict:
    # A plain `def` endpoint: FastAPI runs it in a threadpool, so the 30 to 90
    # second pipeline call does not block the event loop.
    question = _authorize_and_validate(ask)

    q = pc.question_from_text(question)
    try:
        result = pc.build_dossier(q)
    except pc.DailyLimitError:
        raise HTTPException(status_code=429,
                            detail="Tageslimit erreicht. Bitte morgen erneut versuchen.")
    except pc.PraxisError as e:
        raise HTTPException(status_code=422,
                            detail=f"Keine Belege gefunden ({e}).")
    except Exception as e:  # noqa: BLE001  (surface a clean message, log details)
        print(f"praxis error: {type(e).__name__}: {e}", file=sys.stderr)
        raise HTTPException(status_code=500,
                            detail="Interner Fehler bei der Erstellung.")

    return {"dossier": result.dossier,
            "queries": result.queries,
            "count": len(result.selected),
            "citations": pc.citation_view(result.selected)}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/praxis/stream")
def praxis_stream(ask: Ask) -> StreamingResponse:
    """Same guarded pipeline as `/praxis` (it runs `pc.dossier_stages`, the
    exact generator `pc.build_dossier` drains), but emits progress as each
    stage lands instead of blocking for the full 30 to 90 seconds. The 90s is
    inherent to live retrieval (deep 200-paper pool, per-paper enrich, one
    synthesis call) and stays; this only makes the wait visible instead of
    dead. See web/REPLIT_BRIEF.md for the event contract (Work package B1).

    Auth and length validation run here, synchronously, before the stream
    opens, so a bad password or a too-short question still gets a real
    401/400/503 instead of an SSE error event. The daily cap is also
    pre-checked here for the same reason (a real 429 up front covers the
    common case); `dossier_stages` checks it again internally, so the rare
    race where the cap fills mid-stream still surfaces, as an `error` event
    (a real HTTP status is no longer possible once the stream has started)."""
    question = _authorize_and_validate(ask)
    q = pc.question_from_text(question)

    profile_text = pc.PROFILE.read_text(encoding="utf-8")
    try:
        pc.check_daily_cap(pc.daily_cap(profile_text))
    except pc.DailyLimitError:
        raise HTTPException(status_code=429,
                            detail="Tageslimit erreicht. Bitte morgen erneut versuchen.")

    def events():
        try:
            for stage, payload in pc.dossier_stages(q, profile_text=profile_text):
                if stage == "queries":
                    yield _sse("searching", {"queries": payload["queries"]})
                elif stage == "selected":
                    yield _sse("found", {
                        "count": payload["count"],
                        "citations": pc.citation_view(payload["selected"]),
                    })
                elif stage == "synthesis":
                    # Token-by-token streaming is not available: the provider
                    # call (synthesize.run_provider) blocks on
                    # get_final_message() so it can check the Anthropic
                    # `refusal` stop_reason and try the fallback provider
                    # before any text is trusted. So this stage arrives as one
                    # chunk, as soon as the single synthesis call returns.
                    yield _sse("synthesis", {"text": payload["text"]})
                elif stage == "done":
                    yield _sse("done", {
                        "dossier": payload["dossier"],
                        "queries": payload["queries"],
                        "count": len(payload["selected"]),
                        "citations": pc.citation_view(payload["selected"]),
                    })
        except pc.DailyLimitError:
            yield _sse("error", {"status": 429,
                                  "detail": "Tageslimit erreicht. Bitte morgen erneut versuchen."})
        except pc.PraxisError as e:
            yield _sse("error", {"status": 422,
                                  "detail": f"Keine Belege gefunden ({e})."})
        except Exception as e:  # noqa: BLE001  (surface a clean message, log details)
            print(f"praxis stream error: {type(e).__name__}: {e}", file=sys.stderr)
            yield _sse("error", {"status": 500,
                                  "detail": "Interner Fehler bei der Erstellung."})

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",   # Replit/proxy: do not buffer the stream
    })
