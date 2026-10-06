#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "Run ./scripts/setup.sh first."
  exit 1
fi
if [[ ! -f web/dist/index.html ]]; then
  echo "Build the interface first: npm --prefix web ci && npm --prefix web run build"
  exit 1
fi
exec .venv/bin/uvicorn storycompiler.api:app --host 127.0.0.1 --port "${STORY_STUDIO_PORT:-8787}"
