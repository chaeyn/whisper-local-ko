#!/usr/bin/env python3
"""로컬 Whisper M4A 받아쓰기 GUI."""
from __future__ import annotations

import threading
import re
import sys
from pathlib import Path

import argparse
import importlib
import shutil
import queue
import os
import tempfile
import fcntl


def doctor(gui: bool = True) -> bool:
    """모델을 다운로드하지 않고 실행 환경을 검사한다."""
    ok = True
    print(f"Python {sys.version.split()[0]}: {sys.executable}")
    if sys.version_info[:2] != (3, 11):
        print("안내: 검증 기준은 Python 3.11입니다. scripts/setup.sh를 사용하세요.")
    checks = ["whisper", "torch", "transformers", "sentencepiece", "sacremoses"]
    if gui:
        checks.append("tkinter")
    for name in checks:
        try:
            module = importlib.import_module(name)
            if name == "transformers":
                from transformers import MarianMTModel, MarianTokenizer
            if name == "tkinter":
                root = module.Tk()
                root.withdraw()
                root.update()
                root.destroy()
            print(f"[정상] {name}")
        except Exception as exc:
            ok = False
            print(f"[실패] {name}: {exc}")
            if name == "tkinter":
                print("  brew install python-tk@3.11 후 scripts/run.sh로 실행하세요.")
            else:
                print("  scripts/setup.sh로 의존성을 설치하세요.")
    if shutil.which("ffmpeg"):
        print("[정상] FFmpeg")
    else:
        ok = False
        print("[실패] FFmpeg: brew install ffmpeg")
    print("모델 다운로드 및 음성 변환은 검사하지 않았습니다.")
    return ok


def save_transcript(output: Path, text: str, overwrite: bool = False) -> None:
    if not text.strip():
        raise ValueError("인식 결과가 비어 있습니다. 음성 언어와 파일 내용을 확인하세요.")
    # 완성한 임시 파일만 공개한다. TUI 중단 시 기존 결과를 보호한다.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                     prefix=".whisper-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(text.strip() + "\n")
            stream.close()
            if overwrite:
                os.replace(temporary, output)
            else:
                os.link(temporary, output)
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
        raise ValueError(f"오디오 파일을 찾을 수 없습니다: {file_path}")
    output = (output or file_path.with_name(f"{file_path.stem}.ko.txt")).expanduser().resolve()
    if output == file_path:
        raise ValueError("결과 경로는 원본 오디오와 달라야 합니다.")
    if output.exists() and not overwrite:
        raise FileExistsError(f"결과 파일이 있습니다: {output}. 다른 경로 또는 --overwrite를 사용하세요.")
    if not output.parent.is_dir():
        raise ValueError(f"결과 폴더가 없습니다: {output.parent}")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg가 없습니다. brew install ffmpeg를 실행하세요.")
    import whisper
    if progress:
        progress("Loading Whisper", None, None)
    status("Whisper 모델을 불러옵니다. 첫 사용은 다운로드가 필요합니다.")
    cache = Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "whisper"
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / f".{model_size}.download.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        model = whisper.load_model(model_size, device="cpu", download_root=str(cache))
    status("음성을 받아쓰고 있습니다.")
    result = transcribe_with_progress(model, file_path, language, progress)
    recognized = result["text"].strip()
    spoken = result.get("language")
    if not recognized:
        raise ValueError("인식 결과가 비어 있습니다. 음성 언어와 파일 내용을 확인하세요.")
    if spoken == "ko":
        transcript = recognized
    elif spoken == "en":
        status("영한 번역 모델을 불러옵니다. 첫 사용은 다운로드가 필요합니다.")
        if progress:
            progress("Loading translation model", None, None)
        translator = EnglishToKoreanTranslator()
        transcript = translator.translate(recognized, progress=progress) if progress else translator.translate(recognized)
    else:
        raise ValueError(f"감지한 언어: {spoken}. 한국어와 영어 음성만 지원합니다. 음성 언어를 직접 선택해 보세요.")
    if progress:
        progress("Saving", None, None)
    save_transcript(output, transcript, overwrite)
    return transcript, output


LANGUAGES = {
    "자동 감지": None,
    "한국어": "ko",
    "영어": "en",
}
MODELS = ("tiny", "base", "small", "medium", "large")
TRANSLATION_MODEL = "Neurora/opus-hplt-en-ko-v2.0"
TRANSLATION_REVISION = "06f3f7b03a97728560826d7387e1ea25224c65a9"
TRANSLATION_CHUNK_TOKENS = 400


class EnglishToKoreanTranslator:
    """Whisper의 영어 인식 결과를 로컬 번역 모델로 한국어화한다."""

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
        root.title("Whisper 음성 받아쓰기")
        root.geometry("680x490")
        root.minsize(560, 400)

        self.file_path: Path | None = None
        self.busy = False
        self.language = tk.StringVar(value="자동 감지")
        self.model_size = tk.StringVar(value="small")
        self.status = tk.StringVar(value="M4A 파일을 선택하세요. 결과는 한국어로 저장됩니다.")
        self.events: queue.Queue = queue.Queue()
        self.root.after(100, self._poll_events)

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text="M4A 음성을 한국어 텍스트로 변환합니다.").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )

        file_row = ttk.Frame(frame)
        file_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        file_row.columnconfigure(0, weight=1)
        self.file_label = ttk.Label(file_row, text="선택한 파일 없음", anchor="w")
        self.file_label.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.choose_button = ttk.Button(file_row, text="파일 선택", command=self.choose_file)
        self.choose_button.grid(row=0, column=1)

        options = ttk.Frame(frame)
        options.grid(row=2, column=0, sticky="w", pady=(0, 12))
        ttk.Label(options, text="음성 언어").grid(row=0, column=0, padx=(0, 6))
        self.language_box = ttk.Combobox(
            options,
            textvariable=self.language,
            values=tuple(LANGUAGES),
            state="readonly",
            width=12,
        )
        self.language_box.grid(row=0, column=1, padx=(0, 18))
        ttk.Label(options, text="모델").grid(row=0, column=2, padx=(0, 6))
        self.model_box = ttk.Combobox(
            options,
            textvariable=self.model_size,
            values=MODELS,
            state="readonly",
            width=10,
        )
        self.model_box.grid(row=0, column=3)

        self.start_button = ttk.Button(frame, text="변환 시작", command=self.start_transcription)
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
            title="M4A 파일 선택",
            filetypes=[
                ("M4A 오디오", "*.m4a"),
                ("오디오 파일", "*.m4a *.mp3 *.wav *.flac *.ogg"),
                ("모든 파일", "*"),
            ],
        )
        if selected:
            self.file_path = Path(selected)
            self.file_label.configure(text=str(self.file_path))
            self.status.set("준비됨. 변환을 시작할 수 있습니다.")

    def start_transcription(self) -> None:
        if self.busy:
            return
        if self.file_path is None:
            messagebox.showinfo("파일 선택", "먼저 오디오 파일을 선택하세요.")
            return

        output = self.file_path.with_name(f"{self.file_path.stem}.ko.txt")
        overwrite = output.exists()
        if overwrite and not messagebox.askyesno("결과 파일 교체", f"기존 결과를 교체할까요?\n{output}"):
            return
        self.busy = True
        self.start_button.configure(state="disabled")
        self.choose_button.configure(state="disabled")
        self.language_box.configure(state="disabled")
        self.model_box.configure(state="disabled")
        self.status.set("Whisper가 음성을 인식하고 있습니다.")
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
        self.status.set(f"완료: {output_path}")
        self._set_idle()
        messagebox.showinfo("변환 완료", f"텍스트 파일을 저장했습니다.\n{output_path}")

    def _finish_error(self, error: str) -> None:
        self.status.set("변환에 실패했습니다. 설치 안내를 확인하세요.")
        self._set_idle()
        messagebox.showerror(
            "변환 실패",
            "Whisper를 실행하지 못했습니다. README의 설치 안내를 확인하세요.\n\n" + error,
        )

    def _set_idle(self) -> None:
        self.busy = False
        self.start_button.configure(state="normal")
        self.choose_button.configure(state="normal")
        self.language_box.configure(state="readonly")
        self.model_box.configure(state="readonly")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="로컬 음성을 한국어 텍스트로 저장합니다.")
    commands = parser.add_subparsers(dest="command")
    check = commands.add_parser("doctor", help="설치 환경 진단")
    check.add_argument("--no-gui", action="store_true", help="Tk 창 검사 생략")
    commands.add_parser("gui", help="한국어 GUI 실행 (기본)")
    commands.add_parser("tui", help="Run the English terminal UI")
    convert = commands.add_parser("transcribe", help="명령줄 변환")
    convert.add_argument("file", type=Path)
    convert.add_argument("--language", choices=("auto", "ko", "en"), default="auto")
    convert.add_argument("--model", choices=MODELS, default="small")
    convert.add_argument("--output", type=Path)
    convert.add_argument("--overwrite", action="store_true")
    commands.add_parser("live", help="Live microphone captions", add_help=False)
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
        return 0 if doctor(not args.no_gui) else 1
    try:
        if args.command == "tui":
            from whisper_tui import main as tui_main
            tui_main()
        elif args.command == "transcribe":
            _, output = transcribe_file(args.file, args.model,
                                       None if args.language == "auto" else args.language,
                                       args.output, args.overwrite)
            print(f"저장 완료: {output}")
        else:
            global tk, filedialog, messagebox, ttk
            try:
                import tkinter as tk
                from tkinter import filedialog, messagebox, ttk
            except ImportError as exc:
                raise RuntimeError("Tkinter가 없습니다. scripts/setup.sh 후 scripts/run.sh로 실행하세요. CLI는 Tkinter 없이 실행할 수 있습니다.") from exc
            root = tk.Tk()
            WhisperTranscriber(root)
            root.mainloop()
        return 0
    except Exception as exc:
        if args.command == "tui":
            print(f"Error: {exc}", file=sys.stderr)
            print("Check setup: scripts/run.sh doctor --no-gui", file=sys.stderr)
        else:
            print(f"실패: {exc}", file=sys.stderr)
            print("환경 확인: scripts/run.sh doctor", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
