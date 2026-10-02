#!/usr/bin/env python3
"""로컬 Whisper M4A 받아쓰기 GUI."""
from __future__ import annotations

import threading
import re
import sys
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError as exc:
    if exc.name == "_tkinter":
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        raise SystemExit(
            "Tkinter is missing for this Homebrew Python. Install it with:\n"
            f"  brew install python-tk@{python_version}\n"
            "Then run this program again."
        ) from exc
    raise

import whisper


LANGUAGES = {
    "자동 감지": None,
    "한국어": "ko",
    "영어": "en",
}
MODELS = ("tiny", "base", "small", "medium", "large")
TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-tc-big-en-ko"
TRANSLATION_CHUNK_TOKENS = 400


class EnglishToKoreanTranslator:
    """Whisper의 영어 인식 결과를 로컬 번역 모델로 한국어화한다."""

    def __init__(self) -> None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(TRANSLATION_MODEL)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(TRANSLATION_MODEL)
        self.model.eval()

    def translate(self, text: str) -> str:
        import torch

        chunks = self._split_into_chunks(text)
        translated: list[str] = []
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
        self.translator: EnglishToKoreanTranslator | None = None

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

        self.busy = True
        self.start_button.configure(state="disabled")
        self.choose_button.configure(state="disabled")
        self.status.set("Whisper가 음성을 인식하고 있습니다.")
        self.text.delete("1.0", "end")
        file_path = self.file_path
        model_size = self.model_size.get()
        language = LANGUAGES[self.language.get()]
        threading.Thread(
            target=self._transcribe,
            args=(file_path, model_size, language),
            daemon=True,
        ).start()

    def _transcribe(self, file_path: Path, model_size: str, language: str | None) -> None:
        try:
            model = whisper.load_model(model_size)
            result = model.transcribe(
                str(file_path),
                language=language,
                task="transcribe",
                fp16=False,
            )
            spoken_language = result.get("language")
            recognized_text = result["text"].strip()

            if spoken_language == "ko":
                transcript = recognized_text
            else:
                english_text = recognized_text
                if spoken_language != "en":
                    self.root.after(
                        0,
                        self.status.set,
                        "영어 이외의 음성이 감지되어 Whisper가 영어로 옮기고 있습니다.",
                    )
                    english_result = model.transcribe(
                        str(file_path),
                        language=spoken_language,
                        task="translate",
                        fp16=False,
                    )
                    english_text = english_result["text"].strip()

                self.root.after(
                    0,
                    self.status.set,
                    "로컬 번역 모델을 불러와 한국어로 바꾸고 있습니다. 첫 실행은 모델을 내려받습니다.",
                )
                if self.translator is None:
                    self.translator = EnglishToKoreanTranslator()
                transcript = self.translator.translate(english_text)

            output_path = file_path.with_name(f"{file_path.stem}.ko.txt")
            output_path.write_text(transcript + "\n", encoding="utf-8")
            self.root.after(0, self._finish_success, transcript, output_path)
        except Exception as exc:  # Show setup and decoding errors in the GUI.
            self.root.after(0, self._finish_error, str(exc))

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


def main() -> None:
    root = tk.Tk()
    WhisperTranscriber(root)
    root.mainloop()


if __name__ == "__main__":
    main()
