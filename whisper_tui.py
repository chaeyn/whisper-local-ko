"""English terminal UI using the standard curses library."""
from __future__ import annotations

import contextlib
import curses
import locale
import multiprocessing as mp
import os
import queue
import shlex
import sys
import unicodedata
from pathlib import Path

from whisper_m4a import LANGUAGES, MODELS

LANGUAGE_LABELS = ("Auto detect", "Korean", "English")

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".aiff", ".aac", ".mp4"}
HEADER = (
    r" _    _ _   _ ___ ____  ____  _____ ____",
    r"| |  | | | | |_ _/ ___||  _ \| ____|  _ \ ",
    r"| |/\| | |_| || |\___ \| |_) |  _| | |_) |",
    r"|__/\__|_| |_|___|____/|____/|_____|_| \_\ ",
)



def parse_path(value: str) -> Path:
    value = value.strip()
    if not value:
        raise ValueError("Enter an audio file path.")
    # Finder에서 끌어온 따옴표/이스케이프 경로도 받는다.
    if value[0] in "\"'" or "\\ " in value:
        parts = shlex.split(value)
        if len(parts) != 1:
            raise ValueError("Enter one file path at a time.")
        value = parts[0]
    return Path(value).expanduser().resolve()


def wrap_cells(text: str, width: int) -> list[str]:
    """한글의 두 칸 폭을 반영하고 빈 줄을 보존한다."""
    lines = []
    for paragraph in text.split("\n"):
        line, used = "", 0
        for char in paragraph:
            if unicodedata.category(char).startswith("C"):
                char = " "
            size = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in "WF" else 1)
            if used + size > width and line:
                lines.append(line)
                line, used = "", 0
            line += char
            used += size
        lines.append(line)
    return lines


def english_message(message: str) -> str:
    """Localize shared-engine messages without changing Korean transcripts."""
    exact = {
        "Whisper 모델을 불러옵니다. 첫 사용은 다운로드가 필요합니다.": "Loading Whisper. First use requires a model download.",
        "음성을 받아쓰고 있습니다.": "Transcribing audio...",
        "영한 번역 모델을 불러옵니다. 첫 사용은 다운로드가 필요합니다.": "Loading the English-to-Korean model. First use requires a download.",
        "인식 결과가 비어 있습니다. 음성 언어와 파일 내용을 확인하세요.": "No speech was recognized. Check the audio and language setting.",
        "결과 경로는 원본 오디오와 달라야 합니다.": "The output path must differ from the source audio.",
        "FFmpeg가 없습니다. brew install ffmpeg를 실행하세요.": "FFmpeg is missing. Run brew install ffmpeg.",
    }
    if message in exact:
        return exact[message]
    for original, translated in (("오디오 파일을 찾을 수 없습니다: ", "Audio file not found: "),
                                 ("결과 폴더가 없습니다: ", "Output folder not found: ")):
        if message.startswith(original):
            return translated + message[len(original):]
    if message.startswith("감지한 언어: "):
        language = message.split(": ", 1)[1].split(".", 1)[0]
        return f"Detected language: {language}. Only Korean and English are supported. Select the audio language manually."
    if message.startswith("결과 파일이 있습니다: "):
        path = message.split(": ", 1)[1].rsplit(". 다른 경로", 1)[0]
        return f"Output already exists: {path}. Choose another path or confirm replacement."
    return message


def convert_worker(events, source: str, model: str, language: str | None,
                   output: str, overwrite: bool) -> None:
    # curses 화면에는 상태 이벤트만 표시한다. 라이브러리의 출력은 숨긴다.
    from whisper_m4a import transcribe_file
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            text, saved = transcribe_file(Path(source), model, language, Path(output), overwrite,
                                         status=lambda message: events.put(("status", english_message(message))))
        events.put(("success", (text, str(saved))))
    except Exception as exc:
        events.put(("error", english_message(str(exc))))


class Tui:
    def __init__(self, screen):
        self.screen = screen
        self.fields = ["", ""]
        self.focus = 0
        self.editing = False
        self.language = 0
        self.model = MODELS.index("small")
        self.status = "Select an audio file. Results are saved in Korean."
        self.result = ""
        self.saved = ""
        self.scroll = 0
        self.confirm = None
        self.pending = None
        self.process = None
        self.context = mp.get_context("spawn")
        self.events = self.context.Queue()
        self.running = True
        self.browsing = False
        self.directory = Path.cwd()
        self.entries = []
        self.selection = 0
        self.browser_status = ""


    @property
    def busy(self):
        return self.process is not None

    def stop_worker(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join()
            self.process.close()
            self.process = None
        # 종료한 worker의 남은 이벤트가 다음 작업에 섞이지 않게 한다.
        self.events.close()
        self.events = self.context.Queue()

    def start(self):
        try:
            source = parse_path(self.fields[0])
            if not source.is_file():
                raise ValueError(f"File not found: {source}")
            output = parse_path(self.fields[1]) if self.fields[1].strip() else source.with_name(f"{source.stem}.ko.txt")
            if output == source:
                raise ValueError("The output path must differ from the source audio.")
            if not output.parent.is_dir():
                raise ValueError(f"Output folder not found: {output.parent}")
            if output.is_dir():
                raise ValueError("The output path is a folder. Enter a text file path.")
            self.pending = (str(source), MODELS[self.model], list(LANGUAGES.values())[self.language], str(output))
            if output.exists():
                self.confirm = "overwrite"
                self.status = f"Replace the existing result? y: replace / n: cancel | {output}"
            else:
                self.launch(False)
        except (ValueError, OSError) as exc:
            self.status = f"Error: {exc} Fix the path and try again."

    def launch(self, overwrite):
        self.result, self.saved, self.scroll = "", "", 0
        self.status = "Starting conversion. The first model download may take a while."
        self.process = self.context.Process(target=convert_worker, args=(self.events, *self.pending, overwrite), daemon=True)
        try:
            self.process.start()
        except Exception as exc:
            self.process = None
            self.status = f"Error: {exc} Try again."
        self.pending = None

    def poll(self):
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self.status = payload
            elif kind == "success":
                self.result, self.saved = payload
                self.status = "Done. Result saved. Use Up/Down or PgUp/PgDn to read."
            else:
                self.status = f"Error: {payload} Check the path/settings and press s to retry."
        if self.process is not None and not self.process.is_alive():
            self.process.join()
            # 정상 완료 시 Queue feeder가 종료된 후 마지막 이벤트를 읽는다.
            process = self.process
            self.process = None
            self.poll()
            if process.exitcode and not self.status.startswith("Error:"):
                self.status = "Conversion stopped. Run doctor to check the environment and retry."
            process.close()

    def open_browser(self):
        try:
            current = parse_path(self.fields[0]) if self.fields[0].strip() else Path.cwd()
            self.directory = current if current.is_dir() else current.parent
        except (ValueError, OSError):
            self.directory = Path.cwd()
        self.browsing = True
        self.read_directory()

    def read_directory(self):
        try:
            entries = [entry for entry in self.directory.iterdir()
                       if not entry.name.startswith(".") and
                       (entry.is_dir() or entry.suffix.lower() in AUDIO_EXTENSIONS)]
            self.entries = [self.directory.parent] + sorted(entries, key=lambda entry: (not entry.is_dir(), entry.name.casefold()))
            self.selection = 0
            self.browser_status = "Select an audio file and press Enter to attach it."
        except OSError as exc:
            self.entries = [self.directory.parent]
            self.selection = 0
            self.browser_status = f"Cannot read folder: {exc}"

    def browser_key(self, key):
        if key in ("\x1b", "q", "\x03"):
            self.browsing = False
        elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            step = {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -10, curses.KEY_NPAGE: 10}[key]
            self.selection = max(0, min(len(self.entries) - 1, self.selection + step))
        elif key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            self.directory = self.directory.parent
            self.read_directory()
        elif key in ("\n", "\r") and self.entries:
            selected = self.entries[self.selection]
            if selected.is_dir():
                self.directory = selected.resolve()
                self.read_directory()
            elif selected.is_file():
                self.fields[0] = str(selected.resolve())
                self.browsing = False
                self.focus = 0
                self.status = f"Attached: {selected.name}. Press s to convert."
            else:
                self.read_directory()
                self.browser_status = "The file was moved or deleted. Select another file."

    def key(self, key):
        if self.browsing:
            self.browser_key(key)
            return
        if self.confirm:
            if key in ("y", "Y"):
                action, self.confirm = self.confirm, None
                if action == "overwrite":
                    self.launch(True)
                else:
                    self.running = False
            elif key in ("n", "N", "\x1b"):
                self.confirm = None
                self.pending = None
                self.status = "Canceled." if not self.busy else "Conversion continues."
            return
        if self.editing:
            if key in ("\n", "\r", "\x1b"):
                self.editing = False
            elif key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                self.fields[self.focus] = self.fields[self.focus][:-1]
            elif key == "\x15":
                self.fields[self.focus] = ""
            elif isinstance(key, str) and key.isprintable():
                self.fields[self.focus] += key
            return
        if key in ("q", "Q", "\x03"):
            if self.busy:
                self.confirm = "quit"
                self.status = "Stop conversion and quit? y: stop and quit / n: continue"
            else:
                self.running = False
            return
        if key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
            step = {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -10, curses.KEY_NPAGE: 10}[key]
            self.scroll = max(0, self.scroll + step)
        if self.busy:
            return
        if key == "\t":
            self.focus = (self.focus + 1) % 5
        elif key == curses.KEY_BTAB:
            self.focus = (self.focus - 1) % 5
        elif key == "b":
            self.open_browser()
        elif key in ("f", "o"):
            self.focus = 0 if key == "f" else 1
            self.editing = True
        elif key == "l":
            self.language = (self.language + 1) % len(LANGUAGES)
        elif key == "m":
            self.model = (self.model + 1) % len(MODELS)
        elif key == "s":
            self.start()
        elif key in ("\n", "\r"):
            if self.focus == 0:
                self.open_browser()
            elif self.focus == 1:
                self.editing = True
            elif self.focus == 2:
                self.language = (self.language + 1) % len(LANGUAGES)
            elif self.focus == 3:
                self.model = (self.model + 1) % len(MODELS)
            else:
                self.start()

    def draw(self):
        screen = self.screen
        screen.erase()
        height, width = screen.getmaxyx()
        def put(row, text, highlight=False):
            if row >= height - 1:
                return
            clipped = wrap_cells(text, max(1, width - 2))[0]
            try:
                screen.addstr(row, 1, clipped, curses.A_REVERSE if highlight else curses.A_NORMAL)
            except curses.error:
                pass
        if height < 24 or width < 60:
            put(0, "Resize to at least 60 columns x 24 rows. Esc, then q to quit.")
        elif self.browsing:
            put(0, "Attach file | Select audio", True)
            put(2, str(self.directory))
            put(3, "Up/Down: select | Enter: open/attach | Backspace: parent | Esc: cancel")
            room = height - 8
            start = max(0, self.selection - room + 1)
            for index, entry in enumerate(self.entries[start:start + room], start):
                label = "[..] Parent folder" if index == 0 else ("[DIR] " if entry.is_dir() else "[AUDIO] ") + entry.name
                put(5 + index - start, label, index == self.selection)
            put(height - 2, self.browser_status)
        else:
            for row, line in enumerate(HEADER):
                put(row, line)
            put(5, "Local audio -> Korean | b: attach file", True)
            values = [f"Audio: {self.fields[0] or '(b/Enter: browse, f: type path)'}",
                      f"Output: {self.fields[1] or '(<filename>.ko.txt beside source)'}",
                      f"Language: {LANGUAGE_LABELS[self.language]}", f"Model: {MODELS[self.model]}",
                      "Start conversion" + (" (running)" if self.busy else "")]
            for index, value in enumerate(values):
                # 입력 중 긴 경로는 끝부분을 표시한다.
                if self.editing and index == self.focus:
                    value = "Input: ..." + self.fields[index][-max(8, (width - 14) // 2):]
                put(index + 7, value, index == self.focus)
            status = wrap_cells(self.status, width - 2)
            put(13, status[0])
            put(14, status[1] if len(status) > 1 else "")
            put(15, f"Saved: {self.saved}" if self.saved else "Result")
            lines = wrap_cells(self.result or "The Korean result will appear here.", width - 2)
            room = height - 20
            self.scroll = min(self.scroll, max(0, len(lines) - room))
            for index, line in enumerate(lines[self.scroll:self.scroll + room]):
                put(17 + index, line)
            put(height - 3, "Editing: Enter/Esc finish | Ctrl+U clear" if self.editing else "b attach | f path | o output | l language | m model | s start | Tab move")
            put(height - 2, "Up/Down or PgUp/PgDn: scroll | q: quit" + (" | settings locked" if self.busy else ""))
        screen.refresh()

    def run(self):
        self.screen.timeout(100)
        curses.curs_set(0)
        try:
            while self.running:
                self.poll()
                self.draw()
                try:
                    self.key(self.screen.get_wch())
                except curses.error:
                    pass
                except KeyboardInterrupt:
                    self.key("\x03")
        finally:
            self.stop_worker()
            self.events.close()


def main():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("Run the TUI in an interactive terminal: ./scripts/run.sh tui")
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(lambda screen: Tui(screen).run())


if __name__ == "__main__":
    main()
