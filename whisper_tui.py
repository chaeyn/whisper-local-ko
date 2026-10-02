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
import time
from datetime import datetime
from pathlib import Path

from whisper_m4a import LANGUAGES, MODELS

LANGUAGE_LABELS = tuple(LANGUAGES)

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
    # Windows paths use backslashes as separators. POSIX drag-and-drop paths
    # can use shell quotes and escaped spaces.
    if sys.platform == "win32":
        if value[0] in "\"'":
            if value[-1] != value[0] or len(value) < 2:
                raise ValueError("Close the quote around the file path.")
            value = value[1:-1]
    elif value[0] in "\"'" or "\\ " in value:
        parts = shlex.split(value)
        if len(parts) != 1:
            raise ValueError("Enter one file path at a time.")
        value = parts[0]
    if not value:
        raise ValueError("Enter an audio file path.")
    return Path(value).expanduser().resolve()


def wrap_cells(text: str, width: int) -> list[str]:
    """Wrap wide Korean characters and preserve empty lines."""
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
    # Send status events to curses. Suppress library output in the worker.
    from whisper_m4a import transcribe_file
    try:
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            text, saved = transcribe_file(Path(source), model, language, Path(output), overwrite,
                                         status=lambda message: events.put(("status", message)),
                                         progress=lambda stage, done, total: events.put(("progress", (stage, done, total))))
        events.put(("success", (text, str(saved))))
    except Exception as exc:
        events.put(("error", str(exc)))


def progress_bar(progress, width=24, busy=False):
    stage, done, total = progress
    if done is not None and total and total > 0:
        ratio = max(0.0, min(1.0, done / total))
        filled = int(width * ratio)
        return f"[{('#' * filled).ljust(width, '-')}] {ratio:5.0%} {stage}"
    if busy:
        position = int(time.monotonic() * 6) % max(1, width - 3)
        bar = '-' * position + '>>>' + '-' * (width - position - 3)
        return f"[{bar}] {stage}"
    return f"[{'-' * width}] {stage}"


class Tui:
    def __init__(self, screen):
        self.screen = screen
        self.fields = ["", ""]
        self.focus = 0
        self.editing = False
        self.language = 0
        self.model = MODELS.index("small")
        self.status = "Select an audio file. Results are saved in Korean."
        self.progress = ("Ready", None, None)
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
        self.live = False
        self.live_stop = None
        self.quit_after_live = False
        self.device = "default"
        self.devices = [("default", "Default input")]
        self.device_index = 0


    @property
    def busy(self):
        return self.process is not None

    def stop_worker(self):
        if self.process is not None:
            if self.process.is_alive() and self.live and self.live_stop is not None:
                # Give the capture watcher time to stop FFmpeg before a forced
                # worker exit. Windows termination does not run Python finally.
                self.live_stop.set()
                self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
            self.process.join()
            self.process.close()
            self.process = None
        # Discard events from the previous worker before another job starts.
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
        self.progress = ("Starting", None, None)
        self.status = "Starting conversion. The first model download may take a while."
        self.process = self.context.Process(target=convert_worker, args=(self.events, *self.pending, overwrite), daemon=True)
        try:
            self.process.start()
        except Exception as exc:
            self.process = None
            self.status = f"Error: {exc} Try again."
        self.pending = None

    def start_live(self, source=None):
        from whisper_live import live_worker
        try:
            output = parse_path(self.fields[1]) if self.fields[1].strip() else Path.cwd() / f"live-{datetime.now():%Y%m%d-%H%M%S-%f}.ko.txt"
            if output.exists():
                raise ValueError("Live captions need a new output file. Press o to choose a new path.")
            if not output.parent.is_dir():
                raise ValueError(f"Output folder not found: {output.parent}")
            self.result, self.saved, self.scroll = "", "", 0
            self.live_stop = self.context.Event()
            self.process = self.context.Process(target=live_worker,
                args=(self.events, self.live_stop, str(output), MODELS[self.model],
                      list(LANGUAGES.values())[self.language], self.device, source), daemon=True)
            self.process.start()
            self.live = True
            self.progress = ("Starting live captions", None, None)
            self.status = "Loading models, then listening. x: stop and save."
        except Exception as exc:
            self.process = None
            self.live = False
            self.status = f"Error: {exc}"

    def select_device(self):
        try:
            from whisper_live import audio_devices
            if len(self.devices) == 1:
                self.devices += audio_devices()
            self.device_index = (self.device_index + 1) % len(self.devices)
            self.device, name = self.devices[self.device_index]
            self.status = f"Microphone: {name} ({self.device}). v: start live captions."
        except Exception as exc:
            self.status = f"Error: {exc}"

    def finish_live(self):
        self.live_stop.set()
        self.status = "Stopping capture and finishing buffered audio. Completed captions remain saved."

    def poll(self):
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self.status = payload
            elif kind == "progress":
                self.progress = payload
            elif kind == "caption":
                self.result, self.saved = payload
                self.scroll = max(0, len(wrap_cells(self.result, self.screen.getmaxyx()[1] - 2)) - (self.screen.getmaxyx()[0] - 20))
            elif kind == "success":
                self.result, self.saved = payload
                self.progress = ("Done", 1, 1)
                self.status = "Done. Result saved. Use Up/Down or PgUp/PgDn to read."
            else:
                self.progress = ("Failed", None, None)
                self.status = f"Error: {payload} Check the path/settings and press s/v to retry."
        if self.process is not None and not self.process.is_alive():
            self.process.join()
            # Read final events after the worker has flushed its queue.
            process = self.process
            self.process = None
            self.poll()
            if process.exitcode and not self.status.startswith("Error:"):
                self.status = "Conversion stopped. Run doctor to check the environment and retry."
            process.close()
            self.live = False
            self.live_stop = None
            if self.quit_after_live:
                self.running = False

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
                elif self.live:
                    self.quit_after_live = True
                    self.finish_live()
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
            if self.live and key == "x":
                self.finish_live()
            return
        if key == "v":
            self.start_live()
        elif key == "r":
            try:
                source = parse_path(self.fields[0])
                if not source.is_file():
                    raise ValueError(f"File not found: {source}")
                self.start_live(str(source))
            except (ValueError, OSError) as exc:
                self.status = f"Error: {exc}"
        elif key == "d":
            self.select_device()
        elif key == "\t":
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
                      f"Output: {self.fields[1] or '(file: beside source / live: timestamp)'}",
                      f"Language: {LANGUAGE_LABELS[self.language]}", f"Model: {MODELS[self.model]}",
                      ("Live captions (x: stop)" if self.live else "Start conversion") + (" (running)" if self.busy else "")]
            for index, value in enumerate(values):
                # Keep the end of a long path visible during editing.
                if self.editing and index == self.focus:
                    value = "Input: ..." + self.fields[index][-max(8, (width - 14) // 2):]
                put(index + 7, value, index == self.focus)
            status = wrap_cells(self.status, width - 2)
            put(13, status[0])
            put(14, status[1] if len(status) > 1 else "")
            put(12, progress_bar(self.progress, max(8, min(24, width - 35)), self.busy))
            put(15, f"Saved: {self.saved}" if self.saved else "Result")
            lines = wrap_cells(self.result or "The Korean result will appear here.", width - 2)
            room = height - 20
            self.scroll = min(self.scroll, max(0, len(lines) - room))
            for index, line in enumerate(lines[self.scroll:self.scroll + room]):
                put(17 + index, line)
            put(height - 3, "Editing: Enter/Esc finish | Ctrl+U clear" if self.editing else "b attach | f path | o output | l language | m model | s start | Tab move")
            put(height - 2, f"v mic | r replay | d device: {self.device} | x stop | Up/Down scroll | q quit")
        screen.refresh()

    def run(self):
        self.screen.timeout(100)
        with contextlib.suppress(curses.error):
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
        raise RuntimeError("Run the TUI in an interactive terminal: whisper-ko tui")
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(lambda screen: Tui(screen).run())


if __name__ == "__main__":
    main()
