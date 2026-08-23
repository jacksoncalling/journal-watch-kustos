#!/usr/bin/env python3
"""Synthesis providers: the model is a swappable component.

Both backends take the same (system, user) text and return a SynthResult.
Retrieval and all guardrails live in the harness (fetch/rank) and in
synthesize.py post-processing, so switching provider touches no safety logic.

- anthropic: claude-sonnet-4-6 (streaming + get_final_message)
- gemini:    gemini-2.5-flash (fast + cheap over large text; the reason to
             prefer it grows at the full-text and Praxis-Check stages)

VERIFY: the Gemini model id below (`gemini-2.5-flash`) must be confirmed live
with a real key (client.models.list()) before it is trusted, same discipline
as the Europe PMC endpoint. Do not assume it from memory.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"   # VERIFY live before trusting
MAX_TOKENS = 16000


@dataclass
class SynthResult:
    text: str
    input_tokens: int
    output_tokens: int
    refused: bool
    provider: str
    model: str


# --------------------------------------------------------------------------- #
def synth_anthropic(system: str, user: str, model: str, key: str) -> SynthResult:
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},   # 4.6 family: must be explicit
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()

    # "refusal" is a real Anthropic stop_reason (Claude 4+; stop_details is
    # populated only for it). Do not "simplify" this away, see build-plan 5.3.
    refused = msg.stop_reason == "refusal"
    text = "".join(b.text for b in msg.content if b.type == "text")
    return SynthResult(
        text=text,
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
        refused=refused,
        provider="anthropic",
        model=model,
    )


# --------------------------------------------------------------------------- #
def synth_gemini(system: str, user: str, model: str, key: str) -> SynthResult:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=MAX_TOKENS,
        ),
    )

    # Block / refusal detection: no candidates, an explicit block_reason, or a
    # non-STOP finish reason with no text all count as refused.
    refused = False
    pf = getattr(resp, "prompt_feedback", None)
    if pf is not None and getattr(pf, "block_reason", None):
        refused = True
    cands = resp.candidates or []
    if not cands:
        refused = True

    text = ""
    try:
        text = resp.text or ""
    except Exception:
        text = ""
    if cands and not text:
        fr = str(getattr(cands[0], "finish_reason", "") or "").upper()
        if "STOP" not in fr:
            refused = True

    um = getattr(resp, "usage_metadata", None)
    in_tok = getattr(um, "prompt_token_count", 0) or 0
    out_tok = getattr(um, "candidates_token_count", 0) or 0
    return SynthResult(
        text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
        refused=refused,
        provider="gemini",
        model=model,
    )


# --------------------------------------------------------------------------- #
PROVIDERS = {
    "anthropic": synth_anthropic,
    "gemini": synth_gemini,
}

# Which env var holds each provider's key.
KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

DEFAULT_MODEL = {
    "anthropic": DEFAULT_ANTHROPIC_MODEL,
    "gemini": DEFAULT_GEMINI_MODEL,
}
