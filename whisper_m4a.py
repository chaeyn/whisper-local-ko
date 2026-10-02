#!/usr/bin/env python3
"""Local audio transcription with Korean output."""
from __future__ import annotations

import threading
import re
import sys
from pathlib import Path

import argparse
import errno
import importlib
import shutil
import queue
import os
import tempfile
from importlib.metadata import PackageNotFoundError, version

from whisper_platform import model_download_lock


def app_version() -> str:
    try:
        return version("whisper-local-ko")
    except PackageNotFoundError:
        return "0.1.2"


def doctor(gui: bool = True, tui: bool = False) -> bool:
    """Check local dependencies without downloading models or recording audio."""
    ok = True
    print(f"Python {sys.version.split()[0]}: {sys.executable}")
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        ok = False
        print("[FAIL] Python: use Python 3.11 or 3.12.")
    checks = ["whisper", "torch", "transformers", "sentencepiece", "sacremoses", "filelock"]
    if gui:
        checks.append("tkinter")
    if tui:
        checks.append("curses")
    for name in checks:
        try:
            module = importlib.import_module(name)
            if name == "transformers":
                getattr(module, "MarianMTModel")
                getattr(module, "MarianTokenizer")
            if name == "tkinter":
                root = module.Tk()
                try:
                    root.withdraw()
                    root.update()
                finally:
                    root.destroy()
            print(f"[OK] {name}")
        except Exception as exc:
            ok = False
            print(f"[FAIL] {name}: {exc}")
            if name == "tkinter":
                print("  Install Tk support for your Python. A GUI also needs a desktop display.")
                print("  For a terminal-only setup, run: whisper-ko doctor --no-gui --tui")
            elif name == "curses":
                print("  Install windows-curses on Windows. See the installation guide.")
            else:
                print("  Install the project dependencies. See the installation guide.")
    if shutil.which("ffmpeg"):
        print("[OK] FFmpeg")
    else:
        ok = False
        print("[FAIL] FFmpeg: install FFmpeg and add it to PATH.")
    print("This check does not test model downloads, transcription, or microphone access.")
    return ok


def save_transcript(output: Path, text: str, overwrite: bool = False) -> None:
    if not text.strip():
        raise ValueError("No speech was recognized. Check the audio and language setting.")
    # Publish only a complete temporary file. Preserve existing results on failure.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                     prefix=".whisper-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(text.strip() + "\n")
            stream.close()
            if overwrite:
                os.replace(temporary, output)
            else:
                try:
                    os.link(temporary, output)
                except OSError as exc:
                    unsupported = exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EPERM)
                    unsupported = unsupported or getattr(exc, "winerror", None) in (1, 50)
                    if not unsupported:
                        raise
                    raise OSError(
                        exc.errno,
                        f"Could not create the result file: {output}. "
                        "Choose a writable local output folder that supports hard links "
                        "(APFS, ext4, or NTFS).",
                    ) from exc
        finally:
            temporary.unlink(missing_ok=True)


def transcribe_with_progress(model, file_path, language, progress=None):
    if progress is None:
        return model.transcribe(str(file_path), language=language, task="transcribe", fp16=False)
    # Whisper reports completed audio frames through its local tqdm bar.
    # This hook is used only by the TUI's isolated conversion process.
    from types import SimpleNamespace
    from tqdm import tqdm
    module = importlib.import_module("whisper.transcribe")

    class AudioProgress(tqdm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.completed_frames = 0
            progress("Transcribing", 0, self.total)

        def update(self, amount=1):
            self.completed_frames += amount
            progress("Transcribing", min(self.completed_frames, self.total), self.total)
            return super().update(amount)

    original_tqdm = module.tqdm
    module.tqdm = SimpleNamespace(tqdm=AudioProgress)
    try:
        return model.transcribe(str(file_path), language=language, task="transcribe", fp16=False)
    finally:
        module.tqdm = original_tqdm


def transcribe_file(file_path: Path, model_size: str = "small", language: str | None = None,
                    output: Path | None = None, overwrite: bool = False,
                    status=print, progress=None) -> tuple[str, Path]:
    file_path = file_path.expanduser().resolve()
    if not file_path.is_file():
        raise ValueError(f"Audio file not found: {file_path}")
    output = (output or file_path.with_name(f"{file_path.stem}.ko.txt")).expanduser().resolve()
    if output == file_path:
        raise ValueError("The output path must differ from the source audio.")
    if output.is_dir():
        raise ValueError("The output path is a folder. Enter a text file path.")
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {output}. Choose another path or use --overwrite.")
    if not output.parent.is_dir():
        raise ValueError(f"Output folder not found: {output.parent}")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is missing. Install FFmpeg and add it to PATH.")
    import whisper
    if progress:
        progress("Loading Whisper", None, None)
    status("Loading Whisper. First use requires a model download.")
    with model_download_lock(model_size) as cache:
        model = whisper.load_model(model_size, device="cpu", download_root=str(cache))
    status("Transcribing audio.")
    result = transcribe_with_progress(model, file_path, language, progress)
    recognized = result["text"].strip()
    spoken = result.get("language")
    if not recognized:
        raise ValueError("No speech was recognized. Check the audio and language setting.")
    if spoken == "ko":
        transcript = recognized
    elif spoken == "en":
        status("Loading the English-to-Korean model. First use requires a download.")
        if progress:
            progress("Loading translation model", None, None)
        translator = EnglishToKoreanTranslator()
        transcript = translator.translate(recognized, progress=progress) if progress else translator.translate(recognized)
    else:
        raise ValueError(f"Detected language: {spoken}. Only Korean and English are supported. Select the audio language.")
    if progress:
        progress("Saving", None, None)
    save_transcript(output, transcript, overwrite)
    return transcript, output


LANGUAGES = {
    "Auto detect": None,
    "Korean": "ko",
    "English": "en",
}
MODELS = ("tiny", "base", "small", "medium", "large")
TRANSLATION_MODEL = "Neurora/opus-hplt-en-ko-v2.0"
TRANSLATION_REVISION = "06f3f7b03a97728560826d7387e1ea25224c65a9"
TRANSLATION_CHUNK_TOKENS = 400


class EnglishToKoreanTranslator:
    """Translate recognized English text to Korean with a local model."""

    def __init__(self) -> None:
        from transformers import MarianMTModel, MarianTokenizer

        self.tokenizer = MarianTokenizer.from_pretrained(TRANSLATION_MODEL, revision=TRANSLATION_REVISION, token=False)
        self.model = MarianMTModel.from_pretrained(TRANSLATION_MODEL, revision=TRANSLATION_REVISION, token=False)
        self.model.eval()

    def translate(self, text: str, progress=None) -> str:
        import torch

        chunks = self._split_into_chunks(text)
        translated: list[str] = []
        if progress:
            progress("Translating", 0, len(chunks))
        for start in range(0, len(chunks), 4):
            batch_text = chunks[start : start + 4]
            inputs = self.tokenizer(
                batch_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=TRANSLATION_CHUNK_TOKENS + 16,
            )
            with torch.inference_mode():
                output_ids = self.model.generate(
                    **inputs,
                    num_beams=4,
                    max_new_tokens=TRANSLATION_CHUNK_TOKENS + 16,
                )
            translated.extend(
                self.tokenizer.decode(ids, skip_special_tokens=True).strip()
                for ids in output_ids
            )
            if progress:
                progress("Translating", min(start + len(batch_text), len(chunks)), len(chunks))
        return "\n".join(part for part in translated if part)

    def _split_into_chunks(self, text: str) -> list[str]:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", text)
            if sentence.strip()
        ]
        chunks: list[str] = []
        current = ""

        for sentence in sentences:
            token_ids = self.tokenizer.encode(sentence, add_special_tokens=False)
            parts = [
                self.tokenizer.decode(
                    token_ids[index : index + TRANSLATION_CHUNK_TOKENS],
                    skip_special_tokens=True,
                ).strip()
                for index in range(0, len(token_ids), TRANSLATION_CHUNK_TOKENS)
            ] or [sentence]

            for part in parts:
                candidate = f"{current} {part}".strip()
                candidate_tokens = self.tokenizer.encode(candidate, add_special_tokens=False)
                if current and len(candidate_tokens) > TRANSLATION_CHUNK_TOKENS:
                    chunks.append(current)
                    current = part
                else:
                    current = candidate

        if current:
            chunks.append(current)
        return chunks


class WhisperTranscriber:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Whisper Local KO")
        root.geometry("680x490")
        root.minsize(560, 400)

        self.file_path: Path | None = None
        self.busy = False
        self.language = tk.StringVar(value="Auto detect")
        self.model_size = tk.StringVar(value="small")
        self.status = tk.StringVar(value="Select an audio file. Results are saved in Korean.")
        self.events: queue.Queue = queue.Queue()
        self.root.after(100, self._poll_events)

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text="Convert audio to Korean text.").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )

        file_row = ttk.Frame(frame)
        file_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        file_row.columnconfigure(0, weight=1)
        self.file_label = ttk.Label(file_row, text="No file selected", anchor="w")
        self.file_label.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.choose_button = ttk.Button(file_row, text="Select file", command=self.choose_file)
        self.choose_button.grid(row=0, column=1)

        options = ttk.Frame(frame)
        options.grid(row=2, column=0, sticky="w", pady=(0, 12))
        ttk.Label(options, text="Audio language").grid(row=0, column=0, padx=(0, 6))
        self.language_box = ttk.Combobox(
            options,
            textvariable=self.language,
            values=tuple(LANGUAGES),
            state="readonly",
            width=12,
        )
        self.language_box.grid(row=0, column=1, padx=(0, 18))
        ttk.Label(options, text="Model").grid(row=0, column=2, padx=(0, 6))
        self.model_box = ttk.Combobox(
            options,
            textvariable=self.model_size,
            values=MODELS,
            state="readonly",
            width=10,
        )
        self.model_box.grid(row=0, column=3)

        self.start_button = ttk.Button(frame, text="Start transcription", command=self.start_transcription)
        self.start_button.grid(row=3, column=0, sticky="w", pady=(0, 10))

        self.text = tk.Text(frame, wrap="word", height=12, undo=True)
        self.text.grid(row=4, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        scrollbar.grid(row=4, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

        ttk.Label(frame, textvariable=self.status, anchor="w").grid(
            row=5, column=0, sticky="ew", pady=(10, 0)
        )

    def choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[
                ("M4A audio", "*.m4a"),
                ("Audio files", "*.m4a *.mp3 *.wav *.flac *.ogg"),
                ("All files", "*"),
            ],
        )
        if selected:
            self.file_path = Path(selected)
            self.file_label.configure(text=str(self.file_path))
            self.status.set("Ready. Start transcription.")

    def start_transcription(self) -> None:
        if self.busy:
            return
        if self.file_path is None:
            messagebox.showinfo("Select file", "Select an audio file first.")
            return

        output = self.file_path.with_name(f"{self.file_path.stem}.ko.txt")
        overwrite = output.exists()
        if overwrite and not messagebox.askyesno("Replace result", f"Replace the existing result?\n{output}"):
            return
        self.busy = True
        self.start_button.configure(state="disabled")
        self.choose_button.configure(state="disabled")
        self.language_box.configure(state="disabled")
        self.model_box.configure(state="disabled")
        self.status.set("Transcribing audio.")
        self.text.delete("1.0", "end")
        file_path = self.file_path
        model_size = self.model_size.get()
        language = LANGUAGES[self.language.get()]
        threading.Thread(
            target=self._transcribe,
            args=(file_path, model_size, language, overwrite),
            daemon=True,
        ).start()

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status.set(payload)
                elif kind == "success":
                    self._finish_success(*payload)
                else:
                    self._finish_error(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _transcribe(self, file_path: Path, model_size: str, language: str | None,
                    overwrite: bool) -> None:
        try:
            result = transcribe_file(file_path, model_size, language, overwrite=overwrite,
                                    status=lambda text: self.events.put(("status", text)))
            self.events.put(("success", result))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _finish_success(self, transcript: str, output_path: Path) -> None:
        self.text.insert("1.0", transcript)
        self.status.set(f"Saved: {output_path}")
        self._set_idle()
        messagebox.showinfo("Transcription complete", f"The text file was saved.\n{output_path}")

    def _finish_error(self, error: str) -> None:
        self.status.set("Transcription failed. Check the error details.")
        self._set_idle()
        messagebox.showerror(
            "Transcription failed",
            "Whisper could not process the audio. See the error details below.\n\n" + error,
        )

    def _set_idle(self) -> None:
        self.busy = False
        self.start_button.configure(state="normal")
        self.choose_button.configure(state="normal")
        self.language_box.configure(state="readonly")
        self.model_box.configure(state="readonly")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="whisper-ko", description="Convert local audio to Korean text. The default command opens the TUI."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {app_version()}")
    commands = parser.add_subparsers(dest="command")
    check = commands.add_parser("doctor", help="Check the installation")
    check.add_argument("--no-gui", action="store_true", help="Skip the Tk desktop check")
    check.add_argument("--tui", action="store_true", help="Check terminal UI dependencies")
    commands.add_parser("gui", help="Open the desktop interface")
    commands.add_parser("tui", help="Open the terminal interface (default)")
    convert = commands.add_parser("transcribe", help="Transcribe an audio file")
    convert.add_argument("file", type=Path, help="Path to the source audio file")
    convert.add_argument("--language", choices=("auto", "ko", "en"), default="auto", help="Audio language (default: auto)")
    convert.add_argument("--model", choices=MODELS, default="small", help="Whisper model (default: small)")
    convert.add_argument("--output", type=Path, help="Text file path (default: SOURCE.ko.txt)")
    convert.add_argument("--overwrite", action="store_true", help="Replace an existing output file")
    commands.add_parser("live", help="Show live microphone captions", add_help=False)
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "live":
        from whisper_live import main as live_main
        try:
            live_main(argv[1:])
            return 0
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return 0 if doctor(gui=not args.no_gui, tui=args.tui) else 1
    try:
        if args.command in (None, "tui"):
            from whisper_tui import main as tui_main
            tui_main()
        elif args.command == "transcribe":
            _, output = transcribe_file(args.file, args.model,
                                       None if args.language == "auto" else args.language,
                                       args.output, args.overwrite)
            print(f"Saved: {output}")
        else:
            global tk, filedialog, messagebox, ttk
            try:
                import tkinter as tk
                from tkinter import filedialog, messagebox, ttk
            except ImportError as exc:
                raise RuntimeError("Tk support is missing. Install Tk for your Python. See the installation guide.") from exc
            root = tk.Tk()
            WhisperTranscriber(root)
            root.mainloop()
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Check the installation: whisper-ko doctor --no-gui --tui", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
