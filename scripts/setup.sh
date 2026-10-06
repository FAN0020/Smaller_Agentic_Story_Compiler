#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
command -v npm >/dev/null || { echo "Install Node.js 22 or newer."; exit 1; }
uv sync --locked --extra dev --extra local
npm --prefix web ci
npm --prefix web run build
echo "Application installed. Install free local checkpoints with: .venv/bin/python scripts/setup_models.py all"
echo "Start the studio with: ./scripts/start.sh"
