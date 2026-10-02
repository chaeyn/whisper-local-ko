#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v brew >/dev/null; then
  echo 'Homebrew가 필요합니다: https://brew.sh' >&2
  exit 1
fi
brew install python@3.11 python-tk@3.11 ffmpeg
python_bin="$(brew --prefix python@3.11)/bin/python3.11"
if [[ -e .venv ]] && ! .venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 11)' 2>/dev/null; then
  echo '기존 .venv의 Python이 3.11이 아닙니다. 폴더 이름을 바꿔 보존한 뒤 다시 실행하세요.' >&2
  exit 1
fi
"$python_bin" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
exec scripts/run.sh doctor
