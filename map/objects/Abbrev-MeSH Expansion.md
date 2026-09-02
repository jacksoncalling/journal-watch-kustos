---
type: Ghost
status: ghost
kind: unbuilt layer
hub: retrieval-layer
---
# Abbrev-MeSH Expansion

The controlled-vocabulary layer named in 'what's next': map her domain abbreviations to full MeSH entry terms (TCI -> target-controlled infusion, TIVA -> total intravenous anaesthesia, ...) and expand them into queries before search. It would both sharpen the gates and, by making expansion deterministic, cut the residual planner variance. Specced in detail, referenced by the roadmap, not built (confirm against profile.md's Domain-Gate).

would-feed [[Query Planner]] . would-strengthen [[Gate Layer]] . would-map [[MeSH Thesaurus]] . specced-in [[Profile]]

- **Hits:** [[Query Planner]] and [[Gate Layer]]. It sits on the bridge between the LLM seam and the deterministic gates, which is why it is the highest-value ghost to build next.
- **Does not hit:** [[No Embeddings]]. Adding vocabulary expansion is fully inside the no-embeddings design; it is more controlled vocabulary, not a vector store.

Source: CLAUDE.md 'What's next' #1; Josh learning 'consume the thesaurus'.
