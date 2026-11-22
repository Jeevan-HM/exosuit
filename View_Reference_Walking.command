#!/bin/zsh
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
VENV_PYTHON="$PROJECT_DIR/.opensim-venv/bin/python"
TASK_CACHE="${TMPDIR:-/tmp}/exosuite-opensim-cache"
if [[ ! -x "$VENV_PYTHON" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv .opensim-venv --python 3.12 --cache-dir "$TASK_CACHE"
  else
    python3 -m venv .opensim-venv
  fi
fi
if ! "$VENV_PYTHON" -c 'import opensim, matplotlib, PIL' >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$VENV_PYTHON" --cache-dir "$TASK_CACHE" -r opensim_exosuit/requirements-lock.txt
  else
    "$VENV_PYTHON" -m pip install --cache-dir "$TASK_CACHE" -r opensim_exosuit/requirements-lock.txt
  fi
fi
"$VENV_PYTHON" -m opensim_exosuit.live_viewer
if [[ "${EXOSUIT_NO_OPEN:-0}" != "1" ]]; then
  open "$PROJECT_DIR/human_walking/live_walking.html"
fi
