#!/usr/bin/env bash
set -euo pipefail

# Keep the hosted FastAPI app and the pipeline dependencies available after
# task-agent merges. Replit's Nix Python is immutable, so install into the
# project-local site-packages directory already used by this workspace.
PYTHON_VERSION="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
SITE_PACKAGES="${PYTHONUSERBASE:-.pythonlibs}/lib/python${PYTHON_VERSION}/site-packages"
mkdir -p "$SITE_PACKAGES"

# pip is intentionally non-interactive because the post-merge hook runs with
# stdin closed. --target avoids modifying the immutable Nix store.
python -m pip install \
  --disable-pip-version-check \
  --no-input \
  --target "$SITE_PACKAGES" \
  -r requirements.txt \
  -r web/requirements-app.txt

# Catch syntax/import-time compilation issues without starting a second server.
python -m compileall -q scripts web