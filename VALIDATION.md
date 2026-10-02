# Validation

## GitHub release installation update: 0.1.2

Date: 2026-10-02. Local host: macOS Apple Silicon, Python 3.11.17.

- The default suite ran 112 tests: 111 passed and one optional model test was skipped.
- Twenty release installer tests checked archive validation, failed updates, launcher conflicts, paths, and shell input.
- A terminal test passed a fixture installer through a pipe and confirmed that `--run` gave the app a terminal for input.
- Shell checks covered `sh` and `dash`. Python version guards also passed with Python optimization enabled.
- The release preparation script checks version consistency and creates checksums for the wheel, source archive, and installer.

Installer fixture tests use local test downloads. They do not prove that public release assets are available.
The [release installation workflow](https://github.com/chaeyn/whisper-local-ko/actions/workflows/release-install.yml) checks published assets without a source checkout.
Read its completed run and the [v0.1.2 release notes](https://github.com/chaeyn/whisper-local-ko/releases/tag/v0.1.2) for publication checks.
The release notes record the manual terminal check after publication.

## Shell installation update: 0.1.1

Date: 2026-10-02. Host: macOS Apple Silicon, Python 3.11.17.

- `sh scripts/setup.sh --run` installed the package, passed diagnosis, and opened the TUI.
- The TUI exited with `q` and exit code 0.
- `sh` and `dash` syntax checks passed for both shell scripts.
- `dash scripts/run.sh --version` reported 0.1.1.
- `dash scripts/run.sh doctor --no-gui --tui` passed.
- CI creates a new Unix virtual environment through `sh scripts/setup.sh`.
- Shell regression tests check paths, arguments, failure handling, and launch behavior.

## Base runtime checks: 0.1.0

Date: 2026-10-02.

## Local checks

Host: macOS Apple Silicon. Python: 3.11.17.

| Check | Result |
| --- | --- |
| Unit and FFmpeg tests | 83 passed; one optional model test skipped in the default suite |
| Optional model test | Passed separately with `WHISPER_INTEGRATION=1` |
| English speech to Korean | Passed with a synthetic English M4A and the real tiny and translation models |
| Direct English-to-Korean translation | Passed with the pinned translation model |
| Environment check | Whisper, PyTorch, Transformers, SentencePiece, Sacremoses, Filelock, curses, Tk, FFmpeg passed |
| TUI workflow | File browser, tiny Korean conversion, progress, saved result, overwrite cancellation, and quit passed in an interactive terminal |
| File replay and stop | Passed with actual FFmpeg input and a stop event |
| Wheel and source archive | Build and metadata checks passed |
| Installed wheel | Imports and CLI passed outside the source folder |
| Dependency check | No broken requirements |
| Static checks | Fatal syntax/name checks and shell syntax passed |

The model test uses the [credited Korean audio fixture](tests/fixtures/README.md).
It checks file decoding, recognition, Korean output, live file replay, and saved text.
It checks for Korean text and the greeting `안녕`.
This test does not measure general transcription accuracy.

The English speech test produced:

> 안녕하세요, 오늘 우리는 프로젝트 일정과 다음 주에 대한 계획에 대해 논의할 것입니다.

The input sentence was:

> Hello. Today we will discuss the project schedule and our plans for next week.

## Automated platform checks

The [CI workflow](.github/workflows/ci.yml) checks six combinations:

| Runner | Architecture | Python |
| --- | --- | --- |
| macOS 14 | arm64 | 3.11 and 3.12 |
| Ubuntu 24.04 | x64 | 3.11 and 3.12 |
| Windows Server 2022 | x64 | 3.11 and 3.12 |

Each job installs FFmpeg and runs the platform installer.
Each job checks dependencies, tests, documentation links, distributions, and installed wheel imports.
Python 3.11 jobs also run the real Whisper model test.
Job artifacts contain packages and the installed dependency list.

See [GitHub Actions](https://github.com/chaeyn/whisper-local-ko/actions/workflows/ci.yml) for recorded run results.
The platform table states the test scope. Read the run conclusion before you treat a platform check as passed.

## Coverage and limits

Tests cover file protection, UTF-8 text, failed saves, command errors, device parsing, model locks, and worker cleanup.
Tests also cover terminal file selection, overwrite confirmation, progress events, replay, and stop behavior.
Mock tests check the platform-specific device arguments.
Actual FFmpeg tests check file input and cancellation.

Physical microphone recording has not been tested in this release.
Device enumeration on macOS passed. Enumeration does not prove microphone capture.
Windows and Linux hardware permissions and audio-service configuration require a local check.
GUI initialization passed on macOS. The full GUI file-picker workflow has not been tested on Windows or Linux.

The app uses CPU inference.
No GPU, Intel Mac, Linux arm64, Windows arm64, or Python version outside 3.11 and 3.12 is supported in this release.
Long recordings, noise, mixed languages, quiet speech, and chunk-boundary accuracy have not been measured.
Model output can contain errors. Review the saved text.

Output folders must support hard links for safe first-time publication.
Use a local APFS, ext4, or NTFS folder. FAT, exFAT, and some network folders can reject saves.

## Repeat the checks

```bash
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
python -m pip check
python -m ruff check .
python scripts/check_docs.py
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
python scripts/check_wheel.py
python scripts/prepare_release.py
```

Set `WHISPER_INTEGRATION=1` before you run `test_integration.py` to enable model downloads and actual inference.
See the [contribution guide](CONTRIBUTING.md) for commands on each operating system.
