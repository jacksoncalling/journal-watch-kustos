---
type: Capability
status: live
kind: transform
hub: pipeline
---
# Rank

The third stage, pure code, no model. Assigns an evidence level (Stufe 1/2/3) from publication type, then scores by topic match, journal trust, recency, and kanon keyword overlap. This is where the folder-as-database learns her taste: it reads profil/kanon.md via kanon_keywords() and boosts matching papers. 12/12 evidence-mapping tests pass (test_rank.py, the only committed unit tests).

held-by [[The Maintainer]] . depends-on [[Enrich]] . reads [[Kanon]] . reads [[Profile]] . governed-by [[No Embeddings]]

- **Hits:** [[Synthesize]] (it receives the ranked, selected papers). What surfaces in the brief. [[Kanon]] edits change the ranking on the next run.
- **Does not hit:** the [[Gate Layer]]. Rank is the weekly scorer; the Praxis-Check's domain gates are a separate, additive layer and do not run in the weekly path.

Source: scripts/rank.py:96-175; scripts/test_rank.py.
