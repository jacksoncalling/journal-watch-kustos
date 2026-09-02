---
type: Shared Resource
status: live
kind: controlled vocabulary
hub: retrieval-layer
---
# MeSH Thesaurus

The medical thesaurus Kustos consumes instead of building a knowledge graph. MeSH is a professionally maintained controlled vocabulary; the gate layer reads records' MeSH terms to drop off-domain papers and to boost cardiac ones. This is Josh's 'consume the domain thesaurus, don't build a graph' learning made load-bearing: the semantics come from MeSH, not from vectors.

used-by [[Gate Layer]] . would-be-mapped-by [[Abbrev-MeSH Expansion]] . governed-by [[No Embeddings]]

- **Hits:** [[Gate Layer]] behaviour (its whole negative/positive gating reads MeSH). Any future controlled-vocabulary work. The claim that Kustos needs no vector store.
- **Does not hit:** [[Europe PMC]] as a source. MeSH is the vocabulary layered on the records; Europe PMC is where the records come from. Different roles, easy to conflate.

Source: CLAUDE.md 'Current state' (MeSH as thesaurus); Josh learning 'consume the domain thesaurus'.
