---
type: Decision
status: live
kind: architecture
hub: decisions
---
# No Embeddings

The load-bearing architectural choice: retrieval uses no embeddings and no vector store, by design. Boolean Europe PMC + deterministic scoring + string/MeSH matching, with LLM calls only for the query planner and synthesis. This is why the guardrails and provenance can be enforced in code, and why the system is auditable. It is Josh's 'consume the thesaurus, don't build a graph' learning as a product axis.

decides [[Rank]] . decides [[Gate Layer]] . decides [[Query Planner]] . decides [[MeSH Thesaurus]] . decides [[Provider Abstraction]]

- **Hits:** every retrieval stage. Reverse it and you change what can be enforced in code, audited, and reproduced. It is the spine of the determinism story.
- **Does not hit:** [[Synthesize]]'s use of an LLM. 'No embeddings' constrains retrieval, not generation; the one judgment call still uses a model.

Source: CLAUDE.md 'Current state' ('NO embeddings/vector store by design').
