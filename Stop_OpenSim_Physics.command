#!/bin/zsh
# Stop the existing local OpenSim solver, even if Codex started it.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
VENV_PYTHON="$PROJECT_DIR/.opensim-venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
  exec "$VENV_PYTHON" -m opensim_exosuit.stop_physics "$@"
else
  exec python3 -m opensim_exosuit.stop_physics "$@"
fi
