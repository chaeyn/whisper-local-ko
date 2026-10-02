# Whisper Local KO

[한국어](README.ko.md) · [User guide](docs/user-guide.md) · [Contribute](CONTRIBUTING.md) · [Test record](VALIDATION.md)

Convert Korean or English speech to Korean text on your computer.
Select a local audio file, or use a microphone for live captions.

- Use a terminal interface (TUI), a command line (CLI), or a desktop window (GUI).
- Select files with the TUI file browser.
- View progress during file conversion.
- Save UTF-8 text beside the source file, or select an output path.
- Keep audio and transcripts on your computer. No account or API key is required.

The interface uses English. The transcript uses Korean.
Whisper transcribes speech. A local translation model converts English text to Korean.
Review the transcript before you use it.

## Supported environments

| Environment | Architecture | Python | Live audio input |
| --- | --- | --- | --- |
| macOS | Apple Silicon / ARM64 | 3.11, 3.12 | FFmpeg AVFoundation |
| Linux desktop | x86_64 | 3.11, 3.12 | FFmpeg PulseAudio; PipeWire with PulseAudio support |
| Windows | x86_64 | 3.11, 3.12 | FFmpeg DirectShow |

This release uses the CPU. Intel Macs, ARM Linux, and ARM Windows are outside the support target.
The pinned PyTorch release does not provide an Intel macOS wheel.

The TUI needs an interactive terminal with at least 60 columns and 24 rows.
The GUI needs Tk and a desktop session. The CLI can run without a display.
Linux microphone capture needs a running PulseAudio-compatible server.

Automated checks and physical-device tests cover different behavior.
Read [VALIDATION.md](VALIDATION.md) for the tests that passed and the tests that remain unverified.
Physical microphone capture is not verified for this release.

## Install

Install Python 3.11 or 3.12 and FFmpeg first.
Use the GitHub release installer on macOS or Linux. Git is not required.
The first model download needs an internet connection and free disk space.

### macOS

Install [Homebrew](https://brew.sh/) if it is absent.
Run these commands:

```sh
brew install python@3.11 python-tk@3.11 ffmpeg
curl -fsSL https://github.com/chaeyn/whisper-local-ko/releases/latest/download/install.sh | sh -s -- --run
```

### Linux

For Ubuntu 24.04, run these commands:

```sh
sudo apt update
sudo apt install curl python3 python3-venv python3-tk ffmpeg pulseaudio-utils
curl -fsSL https://github.com/chaeyn/whisper-local-ko/releases/latest/download/install.sh | sh -s -- --run
```

For another distribution, install the equivalent packages.
Check that `python3 --version` reports 3.11 or 3.12.
The installer does not install system packages.

The installer downloads a versioned source archive from GitHub Releases.
It verifies the archive against the release's SHA-256 checksum before installation.
It installs under `~/.local/share/whisper-local-ko` and creates `~/.local/bin/whisper-ko`.
It opens the TUI when `--run` is present. Omit `--run` to install only.
To start the app later, run:

```sh
"$HOME/.local/bin/whisper-ko"
```

The installer keeps the previous installation if the new installation fails.
It does not edit your shell profile.
See the [user guide](docs/user-guide.md#release-installer-options) for custom paths, updates, and removal.

### Windows

Use PowerShell. Install the prerequisites:

```powershell
winget install --exact --id Python.Python.3.11
winget install --exact --id Gyan.FFmpeg
```

Open a new PowerShell window. Install the release package:

```powershell
$WhisperVenv = Join-Path $env:LOCALAPPDATA "whisper-local-ko\.venv"
py -3.11 -m venv "$WhisperVenv"
& "$WhisperVenv\Scripts\python.exe" -m pip install --upgrade pip
& "$WhisperVenv\Scripts\python.exe" -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
& "$WhisperVenv\Scripts\python.exe" -m pip install https://github.com/chaeyn/whisper-local-ko/releases/download/v0.1.2/whisper_local_ko-0.1.2-py3-none-any.whl
& "$WhisperVenv\Scripts\whisper-ko.exe" doctor --no-gui --tui
& "$WhisperVenv\Scripts\whisper-ko.exe"
```

For Python 3.12, replace `-3.11` with `-3.12`.
These commands use the release wheel. Git and environment activation are not required.
To start the app in a new PowerShell window, run:

```powershell
& "$env:LOCALAPPDATA\whisper-local-ko\.venv\Scripts\whisper-ko.exe"
```

### Use an existing Python environment

Use a virtual environment with Python 3.11 or 3.12.
On Linux and Windows, install the CPU build of PyTorch first:

```sh
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
```

Then install the wheel from GitHub Releases:

```sh
python -m pip install https://github.com/chaeyn/whisper-local-ko/releases/download/v0.1.2/whisper_local_ko-0.1.2-py3-none-any.whl
whisper-ko doctor --no-gui --tui
whisper-ko
```

The package name is `whisper-local-ko`. The command name is `whisper-ko`.
This method works on each supported OS and does not require a PyPI release.
For source installation and development, read [CONTRIBUTING.md](CONTRIBUTING.md#set-up-a-development-environment).

## Convert a file

Run `"$HOME/.local/bin/whisper-ko"` on macOS or Linux.
On Windows, use the installed executable shown above.

1. Press `b` to open the file browser.
2. Select an audio file.
3. Press `l` to select the speech language.
4. Press `m` to select the model. Use `tiny` for the first check.
5. Press `s` to start conversion.
6. Check the Korean result and the saved path.

The default file model is `small`. The default language is automatic detection.
For short recordings, select `Korean` or `English` to reduce language detection errors.

The app writes `meeting.ko.txt` beside `meeting.m4a`.
Press `o` to select another output path. Create the output folder first.
If a result exists, the TUI asks before it replaces that file.

| Key | Action |
| --- | --- |
| `b` | Browse local files |
| `f` / `o` | Edit the input path / output path |
| `l` / `m` | Select the next language / model |
| `s` | Start file conversion |
| `v` / `d` | Start microphone captions / select a microphone |
| `r` | Process the selected file at its normal time rate |
| `x` | Stop live input and finish buffered audio |
| `↑` / `↓` / `PgUp` / `PgDn` | Scroll the result |
| `q` | Quit; confirm if work is active |

The [user guide](docs/user-guide.md) describes path editing, file selection, progress, and stop behavior.

## Use the CLI or GUI

The examples below use `whisper-ko` on `PATH`.
You can pass the same arguments to the full executable path shown above.
See [Commands and environments](docs/user-guide.md#commands-and-environments) to set `PATH` for the current terminal.

```bash
whisper-ko transcribe "meeting.m4a" --language ko --model small
whisper-ko transcribe "interview.mp3" --language en --output "interview.ko.txt"
whisper-ko gui
whisper-ko doctor
```

The CLI stops if the output file exists.
Add `--overwrite` only when you intend to replace that file.
The GUI asks before it replaces a result.
Save results on a local filesystem with hard-link support, such as APFS, ext4, or NTFS.
For exFAT, FAT, or an unsupported network drive, select an output path in your home folder.

## Use live captions

```bash
whisper-ko live --list-devices
whisper-ko live --language ko --model tiny
```

The live CLI defaults to `tiny`, Korean speech, and six-second audio chunks.
The TUI uses its selected language and model for live captions.
Select `Korean` and `tiny` before you press `v`.

Use `--device` with a device ID from `--list-devices`.
On Windows, `default` selects the first listed DirectShow microphone.
It does not follow the Windows default-device setting.

Press `Ctrl+C` in the live CLI to stop input.
The app finishes buffered audio and saves completed captions.
Live mode needs a new output file. It never replaces an existing result at start.

The first caption takes at least one chunk plus recognition time, after model loading.
Words can be lost at chunk boundaries. Quiet speech can be skipped.
This mode does not provide word-by-word updates or speaker labels.

## Data, models, and help

The app does not send audio or transcript text to a remote service.
Package installation and model downloads contact external servers.
Downloaded models remain in your user cache.
Read [data and model details](docs/user-guide.md#data-and-models) before you remove caches or share diagnostics.

- For setup and device errors, read [Troubleshooting](docs/user-guide.md#troubleshooting).
- For reproducible problems, [open a bug report](https://github.com/chaeyn/whisper-local-ko/issues/new/choose).
- For code, tests, and translations, read [CONTRIBUTING.md](CONTRIBUTING.md).
- For private security reports, read [SECURITY.md](SECURITY.md).

## License and project references

Project code uses the [MIT License](LICENSE).
Whisper and the translation model have their own licenses.
See [model attribution](docs/user-guide.md#model-attribution) and [third-party notices](THIRD_PARTY_NOTICES.md).

[Buzz and Lazygit](docs/project-references.md) informed the documentation structure and contribution guidance.
The documents use an [ASD-STE100-inspired writing style](docs/writing-guide.md).
This project does not claim formal STE compliance or certification.
