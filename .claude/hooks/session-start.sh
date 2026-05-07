#!/bin/bash
# Claude Code on the web SessionStart hook.
#
# Installs Python dependencies for social_distributor/backend so pytest,
# linters, and API smoke checks work the moment the session starts. Only
# runs in Claude Code's remote container — local dev is left alone.
#
# To switch to async (faster session startup, but Claude may try running
# tests before deps finish): replace the no-op below with:
#     echo '{"async": true, "asyncTimeout": 300000}'
# at the top of this script.

set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    exit 0
fi

REPO="${CLAUDE_PROJECT_DIR:-$(pwd)}"
BACKEND="$REPO/social_distributor/backend"

if [ ! -f "$BACKEND/requirements.txt" ]; then
    echo "session-start: $BACKEND/requirements.txt not found, skipping"
    exit 0
fi

echo "session-start: installing Python deps for social_distributor backend..."
python3 -m pip install --quiet -r "$BACKEND/requirements.txt"

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export PYTHONPATH=$BACKEND:\${PYTHONPATH:-}" >> "$CLAUDE_ENV_FILE"
fi

echo "session-start: done"
