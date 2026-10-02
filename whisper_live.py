"""Local microphone captions using FFmpeg and chunked Whisper."""
from __future__ import annotations

import argparse
import contextlib
import os
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time
from datetime import datetime

from whisper_platform import audio_devices, audio_input_arguments, model_download_lock

RATE = 16000


class AudioCapture:
    def __init__(self, device='default', source=None, seconds=6, stop=None):
        self.stop = stop or threading.Event()
        self.chunks = queue.Queue(maxsize=5)
        self.finished = threading.Event()
        self.error = None
        self.size = int(RATE * seconds) * 4
        self.lock = threading.Lock()
        self.closing = threading.Event()
        self.closed = False
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error']
        command += ['-re', '-i', str(source)] if source else audio_input_arguments(device)
        command += ['-vn', '-ac', '1', '-ar', str(RATE), '-f', 'f32le', 'pipe:1']
        self.stderr = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=self.stderr)
        except BaseException as exc:
            self.stderr.close()
            if isinstance(exc, FileNotFoundError):
                raise RuntimeError('FFmpeg was not found. Install FFmpeg and add it to PATH.') from exc
            raise
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.watcher = threading.Thread(target=self.watch, daemon=True)
        try:
            self.thread.start()
            self.watcher.start()
        except BaseException:
            self.closing.set()
            self.halt()
            self.finished.set()
            if self.thread.ident is not None:
                self.thread.join(timeout=5)
            self.process.stdout.close()
            self.stderr.close()
            raise

    def watch(self):
        while not self.finished.wait(0.1):
            if self.stop.is_set():
                self.halt()
                return

    def halt(self):
        with self.lock:
            if self.process.poll() is None:
                try:
                    self.process.terminate()
                except ProcessLookupError:
                    return
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()

    def read(self):
        try:
            while True:
                block = self.process.stdout.read(self.size)
                if not block:
                    break
                try:
                    self.chunks.put_nowait(block)
                except queue.Full:
                    self.error = 'Recognition is slower than capture. Recording stopped; some audio was not processed. Select tiny or base. You can also increase the chunk length.'
                    self.halt()
                    break
            code = self.process.wait()
            if code and not self.stop.is_set() and not self.closing.is_set() and not self.error:
                self.stderr.seek(0)
                detail = self.stderr.read().decode('utf-8', errors='replace')[-1200:]
                self.error = 'Audio input failed. Check FFmpeg, audio access, and the selected input. ' + detail
        except (OSError, ValueError) as exc:
            if not self.stop.is_set() and not self.closing.is_set():
                self.error = f'Could not read audio input: {exc}'
        finally:
            self.finished.set()

    def close(self):
        if self.closed:
            return
        self.closing.set()
        self.halt()
        self.thread.join(timeout=5)
        self.finished.set()
        self.watcher.join(timeout=2)
        self.process.stdout.close()
        self.stderr.close()
        self.closed = True


def run_live(output: Path, model_size='tiny', language='ko', device='default', seconds=6,
             stop=None, emit=lambda kind, payload: None, source=None):
    import numpy as np
    import whisper
    from whisper_m4a import EnglishToKoreanTranslator, save_transcript
    if not 2 <= seconds <= 30:
        raise ValueError('Chunk length must be between 2 and 30 seconds.')
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}. Choose a new path for live captions.')
    if not output.parent.is_dir():
        raise ValueError(f'Output folder not found: {output.parent}')
    if source and not Path(source).is_file():
        raise ValueError(f'Input file not found: {source}')
    stop = stop or threading.Event()
    if stop.is_set():
        return '', ''
    emit('progress', ('Loading Whisper', None, None))
    emit('status', 'Loading Whisper before opening the audio input...')
    with model_download_lock(model_size) as cache:
        model = whisper.load_model(model_size, device='cpu', download_root=str(cache))
    translator = None
    if stop.is_set():
        return '', ''
    if language == 'en':
        emit('status', 'Loading English-to-Korean translation before recording...')
        translator = EnglishToKoreanTranslator()
    if stop.is_set():
        return '', ''
    # Reserve a new output; subsequent atomic writes belong to this session.
    with output.open('x', encoding='utf-8') as reserved:
        reservation = os.fstat(reserved.fileno())
    parts = []
    try:
        capture = AudioCapture(device, source, seconds, stop)
    except BaseException:
        # Remove only this session's empty reservation if startup fails.
        with contextlib.suppress(OSError):
            current = output.stat()
            if (current.st_dev, current.st_ino, current.st_size) == (reservation.st_dev, reservation.st_ino, 0):
                output.unlink()
        raise
    emit('status', f'Listening in {seconds:g}s chunks. x: stop and finish buffered audio.')
    emit('progress', ('Live captions', None, None))
    count = 0
    try:
        while not capture.finished.is_set() or not capture.chunks.empty():
            try:
                block = capture.chunks.get(timeout=0.1)
            except queue.Empty:
                continue
            audio = np.frombuffer(block[:len(block) // 4 * 4], dtype='<f4').copy()
            if len(audio) < RATE // 2 or float(np.sqrt(np.mean(audio ** 2))) < 0.005:
                continue
            count += 1
            started = time.monotonic()
            emit('status', f'Transcribing chunk {count}. Buffered: {capture.chunks.qsize()}.')
            result = model.transcribe(audio, language=language, task='transcribe', fp16=False, verbose=None,
                                      condition_on_previous_text=False)
            text = result['text'].strip()
            if not text:
                continue
            spoken = result.get('language')
            if spoken == 'en':
                if translator is None:
                    emit('status', 'Loading English-to-Korean translation. Capture continues.')
                    translator = EnglishToKoreanTranslator()
                text = translator.translate(text)
            elif spoken != 'ko':
                emit('status', f'Skipped chunk {count}: detected {spoken}. Select Korean or English explicitly.')
                continue
            if text.strip():
                parts.append(text.strip())
                full = '\n'.join(parts)
                save_transcript(output, full, overwrite=True)
                emit('caption', (full, str(output)))
                emit('status', f'Listening. Chunk {count}: {time.monotonic() - started:.1f}s processing. Buffered: {capture.chunks.qsize()}.')
        if capture.error:
            raise RuntimeError(capture.error)
    finally:
        capture.close()
    return '\n'.join(parts), str(output)


def live_worker(events, stop, output, model_size, language, device, source=None):
    # Ensure TUI force-quit also executes capture cleanup.
    def terminate(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    try:
        with open(os.devnull, 'w', encoding='utf-8') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            result = run_live(Path(output), model_size, language, device, stop=stop, source=source,
                              emit=lambda kind, payload: events.put((kind, payload)))
        events.put(('success', result))
    except Exception as exc:
        events.put(('error', str(exc)))
    except KeyboardInterrupt:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog='whisper-ko live', description='Local microphone captions in Korean. Ctrl+C stops recording and finishes buffered audio.')
    parser.add_argument('--list-devices', action='store_true')
    parser.add_argument('--device', default='default', help='Input from --list-devices. Default: system input on macOS/Linux; first input on Windows')
    parser.add_argument('--model', choices=('tiny','base','small','medium','large'), default='tiny')
    parser.add_argument('--language', choices=('ko','en','auto'), default='ko')
    parser.add_argument('--chunk-seconds', type=float, default=6)
    parser.add_argument('--output', type=Path, default=Path(f'live-{datetime.now():%Y%m%d-%H%M%S}.ko.txt'))
    parser.add_argument('--input', type=Path, help='Replay a local audio file as a real-time stream for testing')
    args = parser.parse_args(argv)
    if args.list_devices:
        for index, name in audio_devices(): print(f'{index}: {name}')
        return
    stop = threading.Event()
    original = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *args: stop.set())
    def show(kind, payload):
        if kind == 'caption': print(payload[0].split('\n')[-1], flush=True)
        elif kind == 'status': print(payload, flush=True)
    try:
        _, saved = run_live(args.output, args.model, None if args.language == 'auto' else args.language,
                            args.device, args.chunk_seconds, stop, show, args.input)
        print(f'Saved: {saved}' if saved else 'Stopped before recording.')
    finally:
        signal.signal(signal.SIGINT, original)


if __name__ == '__main__':
    main()
