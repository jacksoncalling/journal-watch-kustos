---
type: meta
role: correction-log
---
# Correction Log

Where a card disagreed with a doc, the **file (code) won** and the card records the
truth. Every entry here is a place the docs had drifted from the code, which is
itself the map's sharpest production finding (see [[Documentation Drift]]). Run
date 2026-09-02, repo at commit `85c284e`.

| # | Doc claim | Code / disk reality | Card verdict |
|---|---|---|---|
| 1 | `CLAUDE.md` known-issue #1: "planner nondeterminism is the main ceiling." | `praxis_check.py:205` sets `temperature=0`; `providers.py:76` sets `seed=7`. Both halves of Josh's "Gemini needs temp+seed" learning are applied. | The [[Query Planner]] is **pinned**. The CLAUDE.md line is stale, superseded by HANDOFF's 2026-08-27 pin. |
| 2 | `HANDOFF.md` gap #9: "Still missing: `04_feedback/CONTEXT.md`." | `04_feedback/CONTEXT.md` exists on disk and is committed. | The CONTEXT **exists**; the *stage* is still unbuilt (its own text says "noch nicht gebaut"). [[Feedback Stage]] is a ghost, but not for the reason the gap list gives. |
| 3 | `HANDOFF.md` TL;DR / gap #3: "Not a git repo / not on GitHub / git init never run." | `origin` = `github.com/jacksoncalling/journal-watch-kustos`; 10+ commits on `main`. | It **is** a pushed git repo. The whole "before ANY push" checklist in the HANDOFF is already spent. |
| 4 | (Territory's own earlier worry) "Missing American journals." | `SRC:MED` is MEDLINE, the US-run index. | Already self-corrected in HANDOFF 2026-08-30. Recorded so the map does not re-raise a dead worry. [[Europe PMC]]. |

**Reading this log:** none of these are bugs in the running system. The pipeline
does what the code says. The drift is entirely in the *documentation layer*, which
is exactly why a cold reader (or model) needs this map: the docs will mislead you,
the code will not, and this map marks where they part.
