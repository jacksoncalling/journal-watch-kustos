---
name: GitHub connector push limits
description: Environment-specific limitation encountered when pushing larger source files through the authenticated GitHub connector.
---

The authenticated GitHub connector is suitable for repository reads and small API writes, but larger HTML payloads may be rejected by the connector gateway before GitHub receives them. The rejection can affect both REST and GraphQL calls, even when the connection itself is healthy.

**Why:** Repeated API attempts failed at the gateway while the same connection successfully handled repository reads and a small blob, so treating the failure as a GitHub permission problem leads to unnecessary reauthorization attempts.

**How to apply:** For source pushes involving larger files, prefer the workspace Git UI or native Git transport after the user authenticates GitHub there. Do not request or paste a token into chat.