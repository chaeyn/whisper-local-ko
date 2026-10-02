#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -P "$(dirname "$0")/.." && pwd)
if [ ! -x "$project_dir/.venv/bin/python" ]; then
  echo 'Install the app with sh scripts/setup.sh. See README.md.' >&2
  exit 1
fi
if command -v brew >/dev/null; then
  python_version="$("$project_dir/.venv/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  tk_prefix="$(brew --prefix "python-tk@$python_version" 2>/dev/null || true)"
  if [ -d "$tk_prefix/libexec" ]; then
    export PYTHONPATH="$tk_prefix/libexec${PYTHONPATH:+:$PYTHONPATH}"
  fi
fi
exec "$project_dir/.venv/bin/python" "$project_dir/whisper_m4a.py" "$@"
