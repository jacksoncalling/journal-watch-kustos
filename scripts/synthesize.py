#!/usr/bin/env python3
"""03_brief: synthesis. The one and only LLM call in the pipeline.

Reads 02_rank/output/selected.json, the brief contract (03_brief/CONTEXT.md)
and profil/profile.md, then makes a single Claude call to write the German
Wochenbrief. Everything else in the pipeline is deterministic code; judgment
is used exactly here.

Model: claude-sonnet-4-6 (4.6 family -> adaptive thinking must be set
explicitly; see build-plan.md 2.7). Streaming + get_final_message() for
timeout safety at max_tokens=16000.

Auth: ANTHROPIC_API_KEY from the environment, or from a gitignored .env in the
repo root (so the key is never pasted into chat and never committed).
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import providers

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "03_brief" / "CONTEXT.md"
PROFILE = ROOT / "profil" / "profile.md"
SELECTED = ROOT / "02_rank" / "output" / "selected.json"
BRIEFE = ROOT / "03_brief" / "briefe"

FOOTER = ("Kein Ersatz für klinische Entscheidungen oder Dosierungsangaben. "
          "Immer Originalquelle und Klinikstandard prüfen.")


# --------------------------------------------------------------------------- #
# auth helper: read a named key from the environment or a gitignored .env
# --------------------------------------------------------------------------- #
def load_env(name: str) -> str | None:
    val = os.environ.get(name)
    if val:
        return val
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, v = line.strip().partition("=")
            if key.strip() == name:            # exact key; ignores comments and
                return v.strip().strip('"').strip("'")   # longer-prefixed vars
    return None


# --------------------------------------------------------------------------- #
# provider config from profile.md
# --------------------------------------------------------------------------- #
def parse_synthese_config(text: str) -> dict:
    def field(name: str, default: str = "") -> str:
        m = re.search(rf"`{name}`\s*:\s*([^\n`#]+)", text)
        return m.group(1).strip() if m else default

    primary = field("synthese_provider", "anthropic") or "anthropic"
    fallback = field("synthese_fallback", "")
    return {
        "primary": primary,
        "fallback": fallback if fallback else None,
        "model": {
            "gemini": field("synthese_model_gemini", providers.DEFAULT_MODEL["gemini"]),
            "anthropic": field("synthese_model_anthropic",
                               providers.DEFAULT_MODEL["anthropic"]),
        },
    }


def run_provider(name: str, system: str, user: str, cfg: dict,
                 temperature: float | None = None):
    """Returns SynthResult, or None if the provider's key is missing.

    `temperature` defaults to None (each provider's own default, unchanged for
    the weekly brief and the dossier). The Praxis-Check planner passes 0 to pin
    query generation to greedy, reproducible decoding."""
    key_env = providers.KEY_ENV.get(name)
    key = load_env(key_env) if key_env else None
    if not key:
        print(f"  [{name}] no {key_env} available, skipping", file=sys.stderr)
        return None
    model = cfg["model"].get(name, providers.DEFAULT_MODEL.get(name))
    fn = providers.PROVIDERS[name]
    try:
        return fn(system, user, model, key, temperature)
    except Exception as e:  # network / API error -> let caller try fallback
        print(f"  [{name}] error: {type(e).__name__}: {e}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# payload construction
# --------------------------------------------------------------------------- #
def provenance(cand: dict) -> str:
    return "[VOLLTEXT]" if cand.get("fullTextExcerpt") else "[NUR ABSTRACT]"


def paper_payload(cand: dict) -> dict:
    """What the model may work from. It writes prose + a [[PMID:...]] anchor;
    it never writes labels or links (code injects those). evidenzstufe is
    given only so the model can calibrate hedging, not to print."""
    return {
        "pmid": cand.get("pmid"),          # the anchor to echo as [[PMID:...]]
        "title": cand.get("title"),
        "journal": cand.get("journal"),
        "date": cand.get("date"),
        "authors": cand.get("authors"),
        "evidenzstufe": cand.get("stufe"),  # context only, do not print
        "evidence_basis": cand.get("fullTextExcerpt") or cand.get("abstract") or "",
    }


def build_user_message(selected: dict) -> str:
    if selected.get("quiet_week"):
        # Use paper_payload here too, so internal fields (score, score_breakdown,
        # stufe) never leak to the model on the quiet-week path.
        quiet_papers = [paper_payload(c) for c in selected.get("selected", [])]
        return ("QUIET_WEEK: Es wurden weniger als 2 relevante Paper gefunden. "
                "Schreibe einen kurzen, ehrlichen Brief, der sagt, dass es eine "
                "ruhige Woche war. Nicht auffüllen, nichts erfinden.\n\n"
                + json.dumps(quiet_papers, ensure_ascii=False))
    papers = [paper_payload(c) for c in selected["selected"]]
    return ("Hier sind die ausgewählten Paper dieser Woche als JSON. Schreibe den "
            "Wochenbrief exakt nach dem Vertrag im System-Prompt. Beende jeden "
            "Paper-Block mit genau `[[PMID:<pmid>]]` (die mitgelieferte PMID). "
            "Schreibe KEINE Stufe-, Provenienz- oder Link-Zeilen; der Code setzt "
            "sie. Arbeite nur mit evidence_basis; wenn dort etwas nicht steht, "
            "lass es weg.\n\n"
            + json.dumps(papers, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- #
# authoritative fact line: built in code from the [[PMID:...]] anchor
# --------------------------------------------------------------------------- #
def fact_line(cand: dict) -> str:
    prov = provenance(cand)
    links = []
    if cand.get("doi"):
        links.append(f"https://doi.org/{cand['doi']}")
    if cand.get("pmid"):
        links.append(f"https://pubmed.ncbi.nlm.nih.gov/{cand['pmid']}")
    if cand.get("oaUrl"):
        links.append(f"OA-PDF: {cand['oaUrl']}")
    return f"[Stufe {cand['stufe']}] {prov}\n" + " · ".join(links)


def inject_facts(brief: str, selected: dict) -> str:
    """Replace each [[PMID:...]] anchor with the code-built fact line. Labels and
    links can only come from here, so the model cannot inflate a Stufe or invent
    a link."""
    # Key only papers that actually have a PMID. str(None) == "None" would
    # collide every PMID-less paper onto one key (and the \d+ anchor regex
    # below never matches "None" anyway), so those must not enter the map.
    by_pmid = {str(c["pmid"]): c for c in selected.get("selected", []) if c.get("pmid")}
    seen: set[str] = set()

    def repl(m: re.Match) -> str:
        pmid = m.group(1)
        seen.add(pmid)
        cand = by_pmid.get(pmid)
        return fact_line(cand) if cand else ""   # unknown anchor -> drop

    # Strip any label tokens the model wrote despite instructions, then inject.
    brief = re.sub(r"\[Stufe\s*\d\]", "", brief)
    brief = re.sub(r"\[(?:NUR ABSTRACT|VOLLTEXT)\]", "", brief)
    out = re.sub(r"\[\[PMID:\s*(\d+)\s*\]\]", repl, brief)

    missing = set(by_pmid) - seen
    if missing:
        print(f"  WARN: {len(missing)} selected paper(s) have no anchor in the "
              f"brief (pmids {sorted(missing)}), the model may have dropped them.",
              file=sys.stderr)
    out = re.sub(r"\n{3,}", "\n\n", out)   # tidy blank runs left by stripping
    return out


# --------------------------------------------------------------------------- #
# post-processing
# --------------------------------------------------------------------------- #
def strip_dashes(text: str) -> str:
    """Enforce the no-em/en-dash rule. Compound hyphens (U+002D) are untouched."""
    text = re.sub(r"\s*[—]\s*", ", ", text)   # em dash -> comma
    text = re.sub(r"\s*[–]\s*", ", ", text)   # en dash -> comma
    return text


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    selected = json.loads(SELECTED.read_text(encoding="utf-8"))
    contract = CONTRACT.read_text(encoding="utf-8")
    profile = PROFILE.read_text(encoding="utf-8")
    cfg = parse_synthese_config(profile)

    system = (contract + "\n\n---\n\n# Profil der Leserin (Kontext)\n\n" + profile)
    user = build_user_message(selected)

    # Primary provider, then fallback on missing key / error / refusal.
    order = [cfg["primary"]] + ([cfg["fallback"]] if cfg["fallback"] else [])
    print(f"provider order: {order}")
    result = None
    for name in order:
        r = run_provider(name, system, user, cfg)
        if r is None:
            continue                      # no key or hard error -> next
        if r.refused:
            print(f"  [{name}] refused (safety). Trying next.", file=sys.stderr)
            continue
        if not r.text.strip():
            print(f"  [{name}] returned empty text. Trying next.", file=sys.stderr)
            continue
        result = r
        break

    if result is None:
        print("No provider produced a brief (missing keys, errors, or refusals). "
              "Nothing written.", file=sys.stderr)
        return 1

    brief = strip_dashes(inject_facts(result.text, selected))
    if FOOTER not in brief:
        brief = brief.rstrip() + "\n\n" + FOOTER + "\n"

    BRIEFE.mkdir(parents=True, exist_ok=True)
    out = BRIEFE / f"{date.today().isoformat()}-wochenbrief.md"
    out.write_text(brief, encoding="utf-8")
    print(f"wrote brief ({result.provider} / {result.model}) -> {out}")
    print(f"tokens: in={result.input_tokens} out={result.output_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
