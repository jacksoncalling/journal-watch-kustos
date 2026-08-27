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
  POST /praxis   -> { question, password } -> { dossier, queries, count }
"""
from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
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


@app.post("/praxis")
def praxis(ask: Ask) -> dict:
    # A plain `def` endpoint: FastAPI runs it in a threadpool, so the 30 to 90
    # second pipeline call does not block the event loop.
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
            "count": len(result.selected)}
