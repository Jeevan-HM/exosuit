#!/bin/zsh
# Primary entry point: actual OpenSim integration + synchronized live knee plot.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$PROJECT_DIR/View_Human_Walking.command" "$@"
