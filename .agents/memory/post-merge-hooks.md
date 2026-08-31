---
name: Post-merge hooks on Nix Python
description: The Replit Nix Python environment is immutable, so post-merge dependency setup must use the project-local package directory.
---

Post-merge Python dependency installation must target the workspace's project-local site-packages directory rather than the system interpreter environment.

**Why:** Replit's Nix Python marks the system environment as externally managed and rejects ordinary pip installs because they attempt to modify the immutable `/nix/store`.

**How to apply:** In a post-merge shell hook, derive the active Python major/minor version and install requirements with pip's `--target` pointing to `.pythonlibs/lib/python<major.minor>/site-packages`. Keep the command non-interactive and idempotent.