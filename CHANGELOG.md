# Changelog

## 0.1.1 - 2026-10-02

- Install and start the app with POSIX `sh`.
- Add `sh scripts/setup.sh --run` to open the TUI after installation.
- Preserve paths with spaces and the caller's working folder.
- Test a new Unix virtual environment through the installation script in CI.

## 0.1.0 - 2026-10-02

First public beta release.

- Save Korean transcripts from Korean audio.
- Translate English speech to Korean with a local model.
- Select files in the terminal UI.
- Show progress during file conversion.
- Capture microphone audio in fixed chunks.
- Save live captions after each completed chunk.
- Support macOS Apple Silicon, Linux x64, and Windows x64.
- Provide English interfaces and English and Korean guides.
- Package the `whisper-ko` command for Python 3.11 and 3.12.
- Protect source files and existing output files.

Read [VALIDATION.md](VALIDATION.md) for test evidence and limits.
