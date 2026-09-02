---
type: Capability
status: live
kind: transform
hub: pipeline
---
# Send

The final stage. Delivers the brief to Telegram, split cleanly at paper boundaries under the 4096-char limit, plain text with tappable links. No 429/retry handling, acceptable for a weekly job and noted as such. --whoami finds the chat id.

held-by [[The Maintainer]] . depends-on [[Synthesize]] . delivers-to [[Telegram]] . reaches [[The Clinician]] . bound-by [[The Guardrails]]

- **Hits:** [[Run Ledgers]]: seen.json is advanced ONLY after Send returns 0, so a failed send retries next week. [[The Clinician]] receiving the brief.
- **Does not hit:** retrieval or ranking. Send is a dumb, careful courier; a send failure loses no papers because the ledger waits for its exit code.

Source: scripts/send_telegram.py; HANDOFF.md gap #8 (no retry).
