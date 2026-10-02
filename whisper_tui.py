"""표준 라이브러리 curses로 실행하는 한국어 터미널 UI."""
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
        raise ValueError("오디오 파일 경로를 입력하세요.")
    # Finder에서 끌어온 따옴표/이스케이프 경로도 받는다.
    if value[0] in "\"'" or "\\ " in value:
        parts = shlex.split(value)
        if len(parts) != 1:
            raise ValueError("파일 경로는 하나씩 입력하세요.")
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


def convert_worker(events, source: str, model: str, language: str | None,
                   output: str, overwrite: bool) -> None:
    # curses 화면에는 상태 이벤트만 표시한다. 라이브러리의 출력은 숨긴다.
    from whisper_m4a import transcribe_file
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            text, saved = transcribe_file(Path(source), model, language, Path(output), overwrite,
                                         status=lambda message: events.put(("status", message)))
        events.put(("success", (text, str(saved))))
    except Exception as exc:
        events.put(("error", str(exc)))


class Tui:
    def __init__(self, screen):
        self.screen = screen
        self.fields = ["", ""]
        self.focus = 0
        self.editing = False
        self.language = 0
        self.model = MODELS.index("small")
        self.status = "오디오 경로를 입력하세요. 결과는 한국어로 저장됩니다."
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
                raise ValueError(f"파일을 찾을 수 없습니다: {source}")
            output = parse_path(self.fields[1]) if self.fields[1].strip() else source.with_name(f"{source.stem}.ko.txt")
            if output == source:
                raise ValueError("결과 경로는 원본 오디오와 달라야 합니다.")
            if not output.parent.is_dir():
                raise ValueError(f"결과 폴더가 없습니다: {output.parent}")
            if output.is_dir():
                raise ValueError("결과 경로가 폴더입니다. 텍스트 파일 경로를 입력하세요.")
            self.pending = (str(source), MODELS[self.model], list(LANGUAGES.values())[self.language], str(output))
            if output.exists():
                self.confirm = "overwrite"
                self.status = f"기존 결과를 교체할까요? y: 교체 / n: 취소 | {output}"
            else:
                self.launch(False)
        except (ValueError, OSError) as exc:
            self.status = f"실패: {exc} 경로를 수정하고 다시 시작하세요."

    def launch(self, overwrite):
        self.result, self.saved, self.scroll = "", "", 0
        self.status = "변환을 시작합니다. 첫 모델 다운로드는 시간이 걸릴 수 있습니다."
        self.process = self.context.Process(target=convert_worker, args=(self.events, *self.pending, overwrite), daemon=True)
        try:
            self.process.start()
        except Exception as exc:
            self.process = None
            self.status = f"실패: {exc} 다시 시작하세요."
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
                self.status = "완료. 결과를 저장했습니다. ↑↓ / PgUp·PgDn으로 읽을 수 있습니다."
            else:
                self.status = f"실패: {payload} 경로·설정을 확인하고 s로 재시도하세요."
        if self.process is not None and not self.process.is_alive():
            self.process.join()
            # 정상 완료 시 Queue feeder가 종료된 후 마지막 이벤트를 읽는다.
            process = self.process
            self.process = None
            self.poll()
            if process.exitcode and not self.status.startswith("실패:"):
                self.status = "변환 프로세스가 종료됐습니다. doctor로 환경을 확인하고 다시 시작하세요."
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
            self.browser_status = "오디오 파일을 골라 Enter로 첨부하세요."
        except OSError as exc:
            self.entries = [self.directory.parent]
            self.selection = 0
            self.browser_status = f"폴더를 읽을 수 없습니다: {exc}"

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
                self.status = f"파일 첨부: {selected.name}. s로 변환을 시작하세요."
            else:
                self.read_directory()
                self.browser_status = "파일이 이동되거나 삭제됐습니다. 다시 선택하세요."

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
                self.status = "취소했습니다." if not self.busy else "변환을 계속합니다."
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
                self.status = "변환을 중단하고 종료할까요? y: 중단 후 종료 / n: 계속"
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
            put(0, "터미널 창을 60열 × 24행 이상으로 늘려주세요. Esc 후 q: 종료")
        elif self.browsing:
            put(0, "파일 첨부 | 오디오 선택", True)
            put(2, str(self.directory))
            put(3, "↑↓ 선택 · Enter 폴더 열기/파일 첨부 · Backspace 상위 · Esc 취소")
            room = height - 8
            start = max(0, self.selection - room + 1)
            for index, entry in enumerate(self.entries[start:start + room], start):
                label = "[..] 상위 폴더" if index == 0 else ("[폴더] " if entry.is_dir() else "[음성] ") + entry.name
                put(5 + index - start, label, index == self.selection)
            put(height - 2, self.browser_status)
        else:
            for row, line in enumerate(HEADER):
                put(row, line)
            put(5, "로컬 음성 → 한국어 | b 파일 첨부", True)
            values = [f"오디오: {self.fields[0] or '(b 또는 Enter로 파일 선택 / f 경로 입력)'}",
                      f"저장: {self.fields[1] or '(원본 옆 <파일명>.ko.txt)'}",
                      f"언어: {list(LANGUAGES)[self.language]}", f"모델: {MODELS[self.model]}",
                      "변환 시작" + (" (실행 중)" if self.busy else "")]
            for index, value in enumerate(values):
                # 입력 중 긴 경로는 끝부분을 표시한다.
                if self.editing and index == self.focus:
                    value = "입력: …" + self.fields[index][-max(8, (width - 14) // 2):]
                put(index + 7, value, index == self.focus)
            status = wrap_cells(self.status, width - 2)
            put(13, status[0])
            put(14, status[1] if len(status) > 1 else "")
            put(15, f"저장 완료: {self.saved}" if self.saved else "결과")
            lines = wrap_cells(self.result or "변환 결과가 여기에 표시됩니다.", width - 2)
            room = height - 20
            self.scroll = min(self.scroll, max(0, len(lines) - room))
            for index, line in enumerate(lines[self.scroll:self.scroll + room]):
                put(17 + index, line)
            put(height - 3, "입력 중: Enter 확정 / Esc 종료 / Ctrl+U 지우기" if self.editing else "b 첨부 · f 경로 · o 저장 · l 언어 · m 모델 · s 시작 · Tab 이동")
            put(height - 2, "↑↓ / PgUp·PgDn 결과 스크롤 · q 종료" + (" · 실행 중 설정 잠금" if self.busy else ""))
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
        raise RuntimeError("TUI는 대화형 터미널에서 실행하세요: ./scripts/run.sh tui")
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(lambda screen: Tui(screen).run())


if __name__ == "__main__":
    main()
