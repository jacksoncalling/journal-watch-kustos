---
type: Shared Resource
status: live
kind: learned memory
hub: memory
---
# Kanon

Her learned taste, one keyword per line. Rank reads it (kanon_keywords) and lightly boosts matching papers, so ranking drifts toward her preferences over time. The output edge is live and wired. The input edge is not: nothing writes to Kanon automatically. Today a human does, which is exactly what makes the [[Feedback Stage]] a ghost.

read-by [[Rank]] . written-by [[The Maintainer]] . should-be-written-by [[Feedback Stage]] . governed-by [[Folder is the Database]]

- **Hits:** [[Rank]]'s per-paper score. Over weeks, which topics float up. The reader who edits it by hand and sees ranking shift.
- **Does not hit:** [[Profile]]'s topics. Kanon nudges ranking; it does not add a topic to fetch. A missing topic is a Profile gap, not a Kanon gap.

Source: profil/kanon.md; scripts/rank.py:147-175.
