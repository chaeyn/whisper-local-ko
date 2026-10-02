# Architecture

[Contributing](../CONTRIBUTING.md) · [Tests](testing.md)

## Components

| File | Responsibility |
| --- | --- |
| `whisper_m4a.py` | Command dispatch, file conversion, model translation, safe output, and Tk GUI |
| `whisper_tui.py` | Terminal layout, file browser, keyboard handling, and worker events |
| `whisper_live.py` | Audio capture, chunk queue, recognition, live output, and stop handling |
| `whisper_platform.py` | Operating-system differences for model locks, microphone discovery, and capture |
| `pyproject.toml` | Package metadata, dependency versions, and `whisper-ko` entry point |
| `scripts/` | Setup, launch, and verification helpers |
| `tests/` | Unit, platform, packaging, and opt-in model tests |

The module names preserve the earlier file-based application layout.
They do not restrict the installed command to M4A or macOS.

## File conversion

The caller validates input and output paths before recognition.
Whisper loads on the CPU. A download lock protects its cache.
The app transcribes the file through FFmpeg and Whisper.
Korean text goes to output. English text passes through the translation model first.
Unsupported languages and empty results produce an error.

The output writer creates a temporary file beside the destination.
For a new result, it publishes the file with an exclusive hard link.
For an approved replacement, it uses an atomic replacement.
The destination filesystem must support the required operation.

## User interfaces

The TUI starts a worker with the multiprocessing `spawn` context.
The worker sends status, progress, caption, result, and error events through a queue.
The main process handles keys and redraws the terminal.
File conversion can terminate the worker after user confirmation.
Live stop uses an event so that queued audio can finish.

The GUI performs conversion in a background thread.
The main thread reads its event queue and updates Tk widgets.
The CLI calls the same file engine directly.

## Live captions

FFmpeg converts input to mono 16 kHz, 32-bit floating-point audio.
A capture thread puts chunks into a bounded queue.
The recognizer loads one Whisper model per session.
It processes chunks in order and saves each completed caption.
The queue holds at most five chunks.

A full queue stops capture and reports lost audio.
A normal stop closes capture, drains retained chunks, and preserves completed captions.
File replay uses FFmpeg's real-time input rate for the same processing path.
Microphone tests must still verify the operating-system backend and permissions.

## Data boundaries

Audio decoding, recognition, translation, and text storage run locally.
Package and model downloads cross the network boundary.
Model weights remain outside the repository.
See [data and models](user-guide.md#data-and-models) for cache behavior.
