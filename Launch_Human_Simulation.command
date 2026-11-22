#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
runtime_dir="$PWD/.venv"
if [[ ! -x "$runtime_dir/bin/python" ]]; then
  python3 -m venv "$runtime_dir"
fi
if ! "$runtime_dir/bin/python" -c 'import mujoco, numpy; assert mujoco.__version__ == "3.4.0"' >/dev/null 2>&1; then
  "$runtime_dir/bin/python" -m pip install -r human/requirements-lock.txt
fi
exec "$runtime_dir/bin/mjpython" -m human.view "$@"
