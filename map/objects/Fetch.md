---
type: Capability
status: live
kind: transform
hub: pipeline
---
# Fetch

The first stage. Queries Europe PMC for each configured topic since the last run, dedupes, and writes candidates.json. Boolean search only, no embeddings. The weekly path bounds it by FIRST_PDATE; the Praxis-Check drops that bound for all-time search. Live-verified against real data.

held-by [[The Maintainer]] . reads-from [[Europe PMC]] . configured-by [[Profile]] . writes [[Run Ledgers]] . would-be-augmented-by [[RSS Fetch]]

- **Hits:** [[Enrich]] (its input), [[Run Ledgers]] (candidates.json + the seen.json dedupe window), the whole downstream chain.
- **Does not hit:** [[Rank]] scoring. Fetch decides what exists, not what is good; changing the query widens or narrows the pool but never reweights it.

Source: scripts/fetch_europepmc.py; HANDOFF.md stage table.
