---
type: Shared Resource
status: live
kind: external corpus
hub: sources
---
# Europe PMC

The literature source of truth. Every candidate comes from a boolean Europe PMC search; SRC:MED is MEDLINE, the US-run index (the 'missing American journals' worry was false). Its results drift over time, which is the un-pinned input side of reproducibility: the code is deterministic, the corpus underneath is not.

read-by [[Fetch]] . annotated-by [[Enrich]] . contested-by [[Determinism vs the LLM Seam]]

- **Hits:** [[Fetch]] and everything downstream. What is even knowable. A query that returns nothing this week may return papers next week.
- **Does not hit:** [[MeSH Thesaurus]]. Europe PMC supplies the records; MeSH is the vocabulary used to filter them. The corpus is not the controlled vocabulary.

Source: scripts/fetch_europepmc.py; HANDOFF.md 2026-08-30 (SRC:MED = MEDLINE).
