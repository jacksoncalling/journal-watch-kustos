---
name: GitHub connector push limits
description: Environment-specific limitation encountered when writing source changes through the authenticated GitHub connector.
---

The authenticated GitHub connector is suitable for repository reads, but source-write requests may be rejected by the connector gateway before GitHub receives them. The rejection can affect REST, GraphQL, and SDK Git-data calls—even for a small first blob—while the connection remains healthy and reports push permission.

**Why:** Repeated API and SDK write attempts failed at the gateway while the same connection successfully handled repository reads and confirmed push permission, so treating the failure as a GitHub permission problem leads to unnecessary reauthorization attempts.

**How to apply:** For source pushes, prefer the workspace Git UI or native Git transport after the user authenticates GitHub there. Do not request or paste a token into chat.