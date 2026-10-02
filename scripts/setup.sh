#!/bin/sh
set -eu

launch_app=false
case "$#:${1:-}" in
  0:) ;;
  1:--run) launch_app=true ;;
  1:--help|1:-h) printf '%s\n' 'Usage: sh scripts/setup.sh [--run]' 'Install the app. Add --run to open the TUI after installation.'; exit 0 ;;
  *) printf '%s\n' 'Usage: sh scripts/setup.sh [--run]' >&2; exit 2 ;;
esac

project_dir=$(CDPATH= cd -P "$(dirname "$0")/.." && pwd)
cd "$project_dir"
if [ -n "${WHISPER_PYTHON:-}" ]; then
  python_bin="$WHISPER_PYTHON"
elif [ "$(uname -s)" = Darwin ] && command -v brew >/dev/null && brew --prefix python@3.11 >/dev/null 2>&1; then
  python_bin="$(brew --prefix python@3.11)/bin/python3.11"
else
  python_bin=python3
fi
if ! "$python_bin" -c 'import sys; assert (3, 11) <= sys.version_info[:2] <= (3, 12)' 2>/dev/null; then
  echo 'Install Python 3.11 or 3.12. See README.md. Set WHISPER_PYTHON to select its path.' >&2
  exit 1
fi
if [ "$(uname -s)" = Darwin ] && [ "$(uname -m)" != arm64 ]; then
  echo 'This release requires Apple Silicon on macOS. Use a native arm64 terminal.' >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null; then
  echo 'Install FFmpeg and add it to PATH. See README.md for your operating system.' >&2
  exit 1
fi
if [ -e .venv ] && ! .venv/bin/python -c 'import sys; assert (3, 11) <= sys.version_info[:2] <= (3, 12)' 2>/dev/null; then
  echo 'The existing .venv is incompatible. Rename it, then run this script again.' >&2
  exit 1
fi
if [ ! -d .venv ]; then
  "$python_bin" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
if [ "$(uname -s)" = Linux ]; then
  .venv/bin/python -m pip install 'torch==2.8.0' --index-url https://download.pytorch.org/whl/cpu
fi
.venv/bin/python -m pip install .
sh "$project_dir/scripts/run.sh" doctor --no-gui --tui
if [ "$launch_app" = true ]; then
  exec sh "$project_dir/scripts/run.sh"
fi
printf '%s\n' 'Installation complete. Run: sh scripts/run.sh'
