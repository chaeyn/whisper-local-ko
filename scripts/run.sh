#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo '설치가 필요합니다: ./scripts/setup.sh' >&2
  exit 1
fi
if command -v brew >/dev/null; then
  tk_prefix="$(brew --prefix python-tk@3.11 2>/dev/null || true)"
  if [[ -d "$tk_prefix/libexec" ]]; then
    export PYTHONPATH="$tk_prefix/libexec${PYTHONPATH:+:$PYTHONPATH}"
  fi
fi
exec .venv/bin/python whisper_m4a.py "$@"
