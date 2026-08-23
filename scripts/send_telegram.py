#!/usr/bin/env python3
"""Send: deliver the latest Wochenbrief to Telegram.

Reads the newest 03_brief/briefe/*-wochenbrief.md, splits it into <=4096-char
messages at paper boundaries (never mid-paper), and sends them via the Telegram
Bot API. Plain text, no parse_mode: Telegram auto-links bare https URLs, so the
DOI/PubMed links stay tappable with zero escaping risk.

Secrets from env or the gitignored .env:
  TELEGRAM_BOT_TOKEN   from @BotFather
  TELEGRAM_CHAT_ID     the chat to send to (use --whoami to find it)

Usage:
  python scripts/send_telegram.py            # send the latest brief
  python scripts/send_telegram.py --whoami   # print chat IDs that messaged the bot
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEFE = ROOT / "03_brief" / "briefe"
LIMIT = 4096
SPACING_S = 0.4


def load_env(name: str) -> str | None:
    val = os.environ.get(name)
    if val:
        return val
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, v = line.strip().partition("=")
            if key.strip() == name:            # exact key, not a prefix match
                return v.strip().strip('"').strip("'")
    return None


def latest_brief() -> Path | None:
    briefe = sorted(BRIEFE.glob("*-wochenbrief.md"))
    return briefe[-1] if briefe else None


def split_messages(text: str, limit: int = LIMIT) -> list[str]:
    """Pack paper blocks (separated by blank lines) into <=limit chunks without
    splitting a block. Hard-split only if a single block exceeds the limit."""
    blocks = text.split("\n\n")
    chunks: list[str] = []
    cur = ""
    for b in blocks:
        if len(b) > limit:                      # oversize single block (rare)
            if cur:
                chunks.append(cur)
                cur = ""
            for i in range(0, len(b), limit):
                chunks.append(b[i:i + limit])
            continue
        add = b if not cur else "\n\n" + b
        if len(cur) + len(add) > limit:
            chunks.append(cur)
            cur = b
        else:
            cur += add
    if cur:
        chunks.append(cur)
    return chunks


def tg_call(token: str, method: str, params: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Telegram {method} HTTP {e.code}: {body}") from None


def whoami(token: str) -> int:
    """Print chat IDs that have messaged the bot (send the bot a message first)."""
    resp = tg_call(token, "getUpdates", {})
    if not resp.get("ok"):
        print("getUpdates failed:", resp, file=sys.stderr)
        return 1
    seen = {}
    for u in resp.get("result", []):
        chat = (u.get("message") or u.get("channel_post") or {}).get("chat", {})
        if chat.get("id") is not None:
            seen[chat["id"]] = chat.get("title") or chat.get("username") \
                or f"{chat.get('first_name','')} {chat.get('last_name','')}".strip()
    if not seen:
        print("No chats found. Send your bot a message first, then re-run --whoami.")
        return 1
    print("Chat IDs that messaged this bot:")
    for cid, who in seen.items():
        print(f"  {cid}   ({who})")
    print("\nPut the right one into TELEGRAM_CHAT_ID in .env")
    return 0


def main(argv: list[str]) -> int:
    token = load_env("TELEGRAM_BOT_TOKEN")
    if not token:
        print("No TELEGRAM_BOT_TOKEN in env or .env. Create a bot with @BotFather, "
              "add its token to .env, then re-run.", file=sys.stderr)
        return 2

    if "--whoami" in argv:
        return whoami(token)

    chat_id = load_env("TELEGRAM_CHAT_ID")
    if not chat_id:
        print("No TELEGRAM_CHAT_ID in env or .env. Run "
              "`python scripts/send_telegram.py --whoami` to find it.",
              file=sys.stderr)
        return 2

    brief_path = latest_brief()
    if not brief_path:
        print("No brief found in 03_brief/briefe/. Run synthesize.py first.",
              file=sys.stderr)
        return 1
    text = brief_path.read_text(encoding="utf-8")
    chunks = split_messages(text)
    print(f"sending {brief_path.name} in {len(chunks)} message(s) to {chat_id}")

    for i, chunk in enumerate(chunks, 1):
        resp = tg_call(token, "sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": "true",
        })
        if not resp.get("ok"):
            print(f"  message {i}/{len(chunks)} failed: {resp}", file=sys.stderr)
            return 1
        print(f"  sent {i}/{len(chunks)} ({len(chunk)} chars)")
        time.sleep(SPACING_S)
    print("delivered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
