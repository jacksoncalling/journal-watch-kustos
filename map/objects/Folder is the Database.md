---
type: Decision
status: live
kind: architecture
hub: decisions
---
# Folder is the Database

The ICM bet: there is no server and no database. Config, learned memory, run state, and every generated brief are Markdown and JSON files in the repo. Truth is small and singular (profile.md, kanon.md, the briefs); generated views are disposable. It is what lets the map ship inside the repo it maps.

decides [[Profile]] . decides [[Kanon]] . decides [[Run Ledgers]]

- **Hits:** how state is stored and versioned. It makes the whole product greppable and diffable, and makes 'the map lives with the code' possible.
- **Does not hit:** the pipeline logic. The storage choice does not change what fetch/rank/synthesize compute; it changes where their inputs and outputs live.

Source: README.md 'How it works'; CLAUDE.md 'Workflow rules' (ICM workspace).
