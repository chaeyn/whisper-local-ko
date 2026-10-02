# User guide

[한국어](user-guide.ko.md) · [Install](../README.md#install)

## Commands and environments

Run `sh scripts/setup.sh` from the repository folder on macOS or Linux.
Add `--run` to install and then open the TUI.
Use `sh scripts/run.sh` to start an installed app.
These commands do not require execute permission on the script files.
It keeps an existing `.venv` if that environment has a supported Python version.
If setup rejects an old environment, rename that `.venv` folder before you run setup again.

On macOS and Linux, activate the environment:

```bash
source .venv/bin/activate
```

On Windows PowerShell, activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use `run.ps1` or `.\.venv\Scripts\whisper-ko.exe` directly.
The examples below assume that the environment is active.
The run scripts accept the same arguments and preserve your current directory.
Relative input and output paths use that directory.

| Command | Purpose |
| --- | --- |
| `whisper-ko` or `whisper-ko tui` | Open the TUI |
| `whisper-ko gui` | Open the desktop window |
| `whisper-ko transcribe FILE` | Convert one local file |
| `whisper-ko live` | Start microphone captions |
| `whisper-ko doctor` | Check dependencies, FFmpeg, and a Tk window |
| `whisper-ko doctor --no-gui --tui` | Check dependencies, FFmpeg, and curses without opening a window |
| `whisper-ko --help` | Show command help |
| `whisper-ko live --help` | Show live-mode options |
| `whisper-ko --version` | Show the app version |

`doctor` does not download models or measure recognition quality.
Success returns exit code `0`. Runtime failure returns `1`. Invalid command arguments return `2`.

## File selection and path editing

The TUI browser lists folders and these file types:
`.m4a`, `.mp3`, `.wav`, `.flac`, `.ogg`, `.aiff`, `.aac`, and `.mp4`.
FFmpeg must support the codec inside the selected file.
The browser omits hidden files.

1. Press `b` to open the browser.
2. Use the arrow keys to select an entry.
3. Press `Enter` to open a folder or select a file.
4. Press `Backspace` to open the parent folder.
5. Press `Esc` to close the browser.

File selection opens a local path. It does not upload the file.

Press `f` to edit the input path. Press `o` to edit the output path.
Paste a path, or type at the end of the existing text.
Use `Backspace` to delete the last character. Use `Ctrl+U` to clear the field.
Press `Enter` or `Esc` to finish editing. Both keys keep the entered value.
Path editing does not support cursor movement within the text.

Use `Tab` and `Shift+Tab` to move between fields.
Press `Enter` to use the selected field.
Surround CLI paths with quotes when they contain spaces.

## Language and model selection

| Mode | Default language | Default model |
| --- | --- | --- |
| TUI file conversion and live captions | Automatic detection | `small` |
| File CLI and GUI | Automatic detection | `small` |
| Live CLI | Korean (`ko`) | `tiny` |

Select `ko` for Korean speech. Select `en` for English speech.
Use `auto` only when automatic language detection is useful.
The app supports Korean and English input.
File conversion fails if automatic detection selects another language.
Live mode skips unsupported-language chunks and shows a status message.

Available models are `tiny`, `base`, `small`, `medium`, and `large`.
Start with `tiny` to check the full workflow.
A larger model needs more memory, disk space, and processing time.
There is no fixed speed or memory guarantee for your device.
This release does not select a GPU.

## Results and progress

File conversion writes `<source-name>.ko.txt` in UTF-8.
Use `--output` in the CLI or `o` in the TUI to change the path.
Create the parent folder first.
The output path must differ from the source audio path.
Use a local output filesystem with hard-link support, such as APFS, ext4, or NTFS.
For exFAT, FAT, or an unsupported network share, save the result in your home folder.

The CLI requires `--overwrite` to replace an existing result.
The TUI and GUI ask for confirmation.
File conversion publishes the completed text with an atomic file operation.
An error before publication leaves the existing result intact.
A forced stop can leave a hidden `.whisper-*` temporary file beside the output.
Close the app before you remove such files.

The TUI shows separate progress stages:

| Stage | Meaning |
| --- | --- |
| Loading | Load or download a model; no measured percentage |
| Transcribing | Ratio of processed audio frames |
| Translating | Ratio of processed text batches |
| Saving | Write the completed result; no measured percentage |
| Done | The operation finished |

Stage progress does not estimate total time or remaining time.
During file conversion, `q` or `Ctrl+C` opens a stop prompt.
Press `y` to terminate the worker and quit. Press `n` to continue.
If conversion finished just before termination, the completed file can already exist.

In the GUI, select a file, language, and model. Then select **Start transcription**.
The GUI displays and saves the result.
Edits in the result box do not update the saved file.
The GUI provides file conversion only.

## Microphone captions

List the available devices:

```bash
whisper-ko live --list-devices
```

Use an ID from that list:

```bash
whisper-ko live --device "DEVICE_ID" --language ko --model tiny --chunk-seconds 6 --output "session.ko.txt"
```

Replace `DEVICE_ID` with the actual ID. Choose a new output path.
The valid chunk length is 2 to 30 seconds. The default is 6 seconds.
The TUI uses six-second chunks.

| System | Input | Device and permission notes |
| --- | --- | --- |
| macOS | AVFoundation audio | Select an index or name. Allow microphone access for the terminal or host app. |
| Linux | PulseAudio | Select a source ID. PipeWire needs its PulseAudio-compatible service. |
| Windows | DirectShow audio | Select a device name. `default` selects the first listed microphone. Allow desktop app microphone access. |

The app loads models before it opens the microphone.
It keeps captured audio in memory. It does not create a raw recording file.
Each completed caption updates the text file.
Without `--output`, live mode creates `live-<timestamp>.ko.txt` in the current directory.
A session with no recognized speech can leave an empty file.

Press `x` in the TUI or `Ctrl+C` in the CLI to stop input.
The app finishes buffered audio before it exits.
A model download or active recognition call can delay the stop.
In the TUI, `q` followed by `y` also finishes buffered audio before exit.

The input queue holds at most five chunks.
If recognition cannot keep up, the app stops input and reports that some audio was not processed.
It keeps completed captions.
Use a smaller model to reduce processing time.
A longer CLI chunk can reduce per-chunk overhead, but increases caption delay.

Live captions can omit words at chunk boundaries.
The silence threshold can omit quiet speech.
Noise, overlapping voices, and mixed languages can produce incorrect text.
This release has no measured accuracy claim for meetings or long recordings.

### Test without a microphone

Process a file at its normal time rate:

```bash
whisper-ko live --input "sample.mp3" --language ko --model tiny --output "replay.ko.txt"
```

In the TUI, select a file and press `r`.
This test feeds audio to the recognizer. It does not play sound through the speakers.
File replay does not verify microphone permissions or physical capture.

## Data and models

The app runs recognition and translation locally.
It does not upload audio or transcript text.
Package installers and model download clients contact their distribution servers.
Those servers can receive normal request information, such as your IP address.
The app does not require an account or API key.

Whisper models use `$XDG_CACHE_HOME/whisper` when `XDG_CACHE_HOME` is set.
Otherwise, they use `~/.cache/whisper`, including on Windows.
The translation client uses the Hugging Face cache, normally `~/.cache/huggingface/hub`.
Hugging Face environment settings can change that location.

Use a cached model to avoid downloading its weights again.
Hugging Face can still check model metadata while online.
For a cached translation model, set `HF_HUB_OFFLINE=1` to prevent those requests.
An incomplete cache fails in offline mode.

Audio files and transcripts remain until you delete them.
They can contain private information.
Remove private paths and text before you share logs or screenshots.

## Model attribution

- [OpenAI Whisper](https://github.com/openai/whisper) provides speech recognition. Its code and model weights use the MIT License.
- [Neurora/opus-hplt-en-ko-v2.0](https://huggingface.co/Neurora/opus-hplt-en-ko-v2.0) provides English-to-Korean translation under CC BY 4.0.
- The translation model converts [HPLT/translate-en-ko-v2.0-hplt_opus](https://huggingface.co/HPLT/translate-en-ko-v2.0-hplt_opus) for Transformers.
- The app pins translation revision `06f3f7b03a97728560826d7387e1ea25224c65a9`.

The repository does not include model weights.
The project MIT License does not replace model or dependency licenses.
FFmpeg license terms depend on the installed build.
See the [FFmpeg legal page](https://ffmpeg.org/legal.html) if you redistribute FFmpeg.
The test audio has separate attribution in `tests/fixtures/`.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Python version error | Install Python 3.11 or 3.12. Preserve the old `.venv` by renaming it, then run setup. |
| `whisper-ko` is not found | Activate `.venv`, or use the run script. |
| FFmpeg is not found | Install FFmpeg. Open a new terminal if the installer changed `PATH`. |
| Tk import error on macOS | Install the matching Homebrew `python-tk` package. Use `run.sh`. |
| Tk import error on Linux | Install the matching Python Tk package. |
| No display on Linux | Use CLI/TUI. Use `doctor --no-gui --tui` for diagnosis. |
| TUI does not open | Use an interactive terminal. Enlarge it to 60 × 24 or more. |
| Windows curses import fails | Run setup again with the supported Python interpreter. |
| Result already exists | Select a new path, or explicitly confirm replacement for file conversion. |
| First run seems slow | Wait for model download and loading. Check the network and free disk space. |
| Empty or incorrect result | Select the speech language. Check the audio level and recording quality. |
| Live input is too slow | Select `tiny`. Close other CPU-intensive programs. |
| Microphone input fails | Check the device ID and the operating system microphone permission. |
| Linux has no microphone source | Start the PulseAudio-compatible service in your desktop session. Check `pactl list short sources`. |

For a bug report, include the app version, OS, CPU architecture, Python version, command, and complete error.
Add the model, input language, and `doctor` result.
Share only audio that you have permission to publish.

## Update or remove the app

To update a source installation, keep a backup of your results.
Pull the intended release into the repository. Run the setup script again.
Do not overwrite your own source changes without review.

To remove the package from an active environment, run:

```bash
python -m pip uninstall whisper-local-ko
```

A dedicated `.venv` can be deleted after the app exits.
Keep source audio and transcripts that you still need.
The uninstall command does not remove models, system Python, Tk, or FFmpeg.
Remove only the model cache folders you no longer need.
Other applications can share those caches.
