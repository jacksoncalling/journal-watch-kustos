---
type: meta
role: correction-log
---
# Correction Log

Where a card disagreed with reality, the source of truth won and the card was
fixed. The first four entries are doc-vs-code drift found on the first pass (run
2026-09-02, commit `85c284e`). Entries 5 and 6 are the rerun (2026-09-02, after
syncing 14 Replit commits and a fact from the maintainer): the deployment and the
running app won over the repo's docs and over the map's own first reading.

| # | Claim | Reality | Verdict |
|---|---|---|---|
| 1 | `CLAUDE.md` known-issue #1: "planner nondeterminism is the main ceiling." | `praxis_check.py:205` temp 0 + `providers.py:76` seed 7. | [[Query Planner]] is **pinned**. The CLAUDE.md line is stale. |
| 2 | `HANDOFF.md` gap #9: "`04_feedback/CONTEXT.md` still missing." | It exists and is committed. | The file exists; the *stage* is still unbuilt. [[Feedback Stage]]. |
| 3 | `HANDOFF.md`: "Not a git repo / not on GitHub." | Pushed repo with full history. | It is a pushed git repo. |
| 4 | (Earlier worry) "Missing American journals." | `SRC:MED` is MEDLINE (US index). | Dead worry; not re-raised. [[Europe PMC]]. |
| 5 | **This map, first pass: "[[The Clinician]] is a ghost; no real user exists."** | The published Replit app is used by the maintainer's partner and two other physicians (maintainer, 2026-09-02). | **Wrong.** The served user is **live**. The map read this repo's docs (Dr. Demo, "step 8") as the product's state; the deployment overrides them. The absence moved to [[Real Instantiation]] (the personalization), a new ghost. |
| 6 | This map, first pass: "[[Presentation over Retrieval]]: the cheap frontend wins are still to do." | Replit rebuilt `web/index.html` (+1046 lines): inspectable citations, SSE progress, a chat-history panel; app published. | Largely **done**. The gradient spent itself in the predicted direction; the card now records it as realized. |

**The lesson these entries carry:** the docs (and this map's first reading of
them) described a product that was not yet serving anyone. The running deployment
tells a different story, and it wins. This is [[Documentation Drift]] at the
product level, and it is why a live territory needs its cards dated and re-walked,
not trusted once.
