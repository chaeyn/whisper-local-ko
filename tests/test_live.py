import queue
import io
import shutil
import subprocess
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import whisper_live as live


class FakeCapture:
    error = None
    def __init__(self, *args):
        self.chunks = queue.Queue()
        for _ in range(2):
            self.chunks.put(np.full(live.RATE, 0.1, dtype='<f4').tobytes())
        self.finished = threading.Event()
        self.finished.set()
        self.closed = False
    def close(self): self.closed = True


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.output = Path(self.folder.name) / 'live.ko.txt'
        self.model = Mock()
        self.model.transcribe.side_effect = [
            {'language':'ko', 'text':'첫 문장'}, {'language':'ko', 'text':'다음 문장'}]
        self.whisper = Mock()
        self.whisper.load_model.return_value = self.model

    def run_stream(self, capture=FakeCapture, language='ko', stop=None):
        events=[]
        with patch.dict('sys.modules', {'whisper': self.whisper}), patch.object(live, 'AudioCapture', capture):
            result = live.run_live(self.output, language=language, stop=stop,
                                   emit=lambda *event: events.append(event))
        return result, events

    def test_captions_are_saved_incrementally_and_model_loads_once(self):
        result, events = self.run_stream()
        self.assertEqual(self.whisper.load_model.call_count, 1)
        captions = [payload for kind,payload in events if kind=='caption']
        self.assertEqual([text for text,path in captions], ['첫 문장', '첫 문장\n다음 문장'])
        self.assertEqual(self.output.read_text(encoding='utf-8'), result[0]+'\n')

    def test_existing_result_is_never_replaced(self):
        self.output.write_text('기존', encoding='utf-8')
        with self.assertRaises(FileExistsError): self.run_stream()
        self.assertEqual(self.output.read_text(encoding='utf-8'), '기존')
        self.whisper.load_model.assert_not_called()

    def test_stop_before_capture_creates_no_output(self):
        stop=threading.Event(); stop.set()
        with patch.object(live, 'AudioCapture') as capture:
            result,events=self.run_stream(capture=capture, stop=stop)
            capture.assert_not_called()
        self.assertEqual(result, ('',''))
        self.assertFalse(self.output.exists())

    def test_capture_error_keeps_completed_captions(self):
        class FailedCapture(FakeCapture): error='Permission denied'
        with self.assertRaisesRegex(RuntimeError, 'Permission denied'):
            self.run_stream(capture=FailedCapture)
        self.assertIn('첫 문장', self.output.read_text(encoding='utf-8'))

    def test_english_translates_locally(self):
        self.model.transcribe.side_effect=[{'language':'en','text':'Hello'}]*2
        with patch('whisper_m4a.EnglishToKoreanTranslator') as translator:
            translator.return_value.translate.return_value='안녕하세요'
            result,events=self.run_stream(language='en')
            translator.assert_called_once()
            self.assertEqual(translator.return_value.translate.call_count,2)
        self.assertEqual(result[0], '안녕하세요\n안녕하세요')

    def test_backlog_limit_stops_capture_without_silent_loss(self):
        process = Mock()
        process.stdout = io.BytesIO(np.full(live.RATE * 2 * 7, 0.1, dtype='<f4').tobytes())
        process.poll.return_value = 0
        process.wait.return_value = 0
        with patch.object(live.subprocess, 'Popen', return_value=process):
            capture = live.AudioCapture(seconds=2, source='test.wav')
            capture.thread.join(timeout=2)
            self.assertEqual(capture.chunks.qsize(), 5)
            self.assertIn('some audio was not processed', capture.error)
            capture.close()

    def test_invalid_chunk_length_rejected(self):
        with patch.dict('sys.modules', {'whisper': self.whisper}):
            with self.assertRaises(ValueError): live.run_live(self.output, seconds=0)
        self.whisper.load_model.assert_not_called()

    def test_capture_start_failure_removes_empty_result_reservation(self):
        with self.assertRaisesRegex(RuntimeError, 'No microphone'):
            self.run_stream(capture=Mock(side_effect=RuntimeError('No microphone')))
        self.assertFalse(self.output.exists())

    def test_capture_start_failure_keeps_a_result_changed_by_another_writer(self):
        def fail_after_external_write(*args):
            self.output.write_text('External update', encoding='utf-8')
            raise RuntimeError('No microphone')
        with self.assertRaisesRegex(RuntimeError, 'No microphone'):
            self.run_stream(capture=fail_after_external_write)
        self.assertEqual(self.output.read_text(encoding='utf-8'), 'External update')

    def test_stop_during_model_load_does_not_open_audio(self):
        stop = threading.Event()
        def load_model(*args, **kwargs):
            stop.set()
            return self.model
        self.whisper.load_model.side_effect = load_model
        capture = Mock()
        result, _ = self.run_stream(capture=capture, stop=stop)
        self.assertEqual(result, ('', ''))
        capture.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_transcription_failure_closes_capture_and_preserves_saved_text(self):
        self.model.transcribe.side_effect = [{'language': 'ko', 'text': '저장한 문장'}, RuntimeError('Model failure')]
        capture = FakeCapture()
        with self.assertRaisesRegex(RuntimeError, 'Model failure'):
            self.run_stream(capture=Mock(return_value=capture))
        self.assertTrue(capture.closed)
        self.assertEqual(self.output.read_text(encoding='utf-8'), '저장한 문장\n')

    def test_ffmpeg_start_failure_closes_temporary_file(self):
        stderr = io.BytesIO()
        with patch.object(live.tempfile, 'TemporaryFile', return_value=stderr):
            with patch.object(live.subprocess, 'Popen', side_effect=FileNotFoundError):
                with self.assertRaisesRegex(RuntimeError, 'Install FFmpeg'):
                    live.AudioCapture(source='test.wav')
        self.assertTrue(stderr.closed)

    def test_thread_start_failure_closes_process_resources(self):
        stderr = io.BytesIO()
        process = Mock(stdout=io.BytesIO(b''))
        process.poll.return_value = 0
        thread = Mock(ident=None)
        thread.start.side_effect = RuntimeError('Cannot start thread')
        with patch.object(live.tempfile, 'TemporaryFile', return_value=stderr):
            with patch.object(live.subprocess, 'Popen', return_value=process):
                with patch.object(live.threading, 'Thread', return_value=thread):
                    with self.assertRaisesRegex(RuntimeError, 'Cannot start thread'):
                        live.AudioCapture(source='test.wav')
        self.assertTrue(stderr.closed)
        self.assertTrue(process.stdout.closed)

    def test_replay_does_not_use_a_platform_microphone_backend(self):
        process = Mock(stdout=io.BytesIO(b''))
        process.poll.return_value = 0
        process.wait.return_value = 0
        with patch.object(live, 'audio_input_arguments', side_effect=AssertionError('Microphone opened')):
            with patch.object(live.subprocess, 'Popen', return_value=process) as popen:
                capture = live.AudioCapture(source='file with spaces.wav')
                capture.thread.join(timeout=2)
                capture.close()
        command = popen.call_args.args[0]
        self.assertIn('file with spaces.wav', command)
        self.assertIn('-re', command)

    def test_failed_ffmpeg_read_reports_error_and_closes(self):
        process = Mock()
        process.stdout.read.side_effect = OSError('Input disconnected')
        process.poll.return_value = 0
        process.wait.return_value = 0
        with patch.object(live.subprocess, 'Popen', return_value=process):
            capture = live.AudioCapture(source='test.wav')
            capture.thread.join(timeout=2)
            self.assertTrue(capture.finished.is_set())
            self.assertIn('Input disconnected', capture.error)
            capture.close()
            capture.close()
        process.stdout.close.assert_called_once()

    def test_halt_kills_ffmpeg_if_terminate_times_out(self):
        capture = live.AudioCapture.__new__(live.AudioCapture)
        capture.lock = threading.Lock()
        capture.process = Mock()
        capture.process.poll.return_value = None
        capture.process.wait.side_effect = [subprocess.TimeoutExpired('ffmpeg', 3), 0]
        capture.halt()
        capture.process.terminate.assert_called_once()
        capture.process.kill.assert_called_once()

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is not installed')
    def test_real_file_replay_reads_float_audio_and_closes_resources(self):
        source = Path(self.folder.name) / '한글 audio.wav'
        samples = np.full(live.RATE, 4096, dtype='<i2')
        with wave.open(str(source), 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(live.RATE)
            audio.writeframes(samples.tobytes())
        capture = live.AudioCapture(source=source, seconds=2)
        try:
            self.assertTrue(capture.finished.wait(timeout=10))
            self.assertIsNone(capture.error)
            block = capture.chunks.get_nowait()
            actual = np.frombuffer(block, dtype='<f4')
            self.assertEqual(len(actual), live.RATE)
            self.assertAlmostEqual(float(actual.mean()), 0.125, places=5)
        finally:
            capture.close()
        self.assertIsNotNone(capture.process.poll())
        self.assertTrue(capture.process.stdout.closed)
        self.assertTrue(capture.stderr.closed)
        self.assertFalse(capture.thread.is_alive())
        self.assertFalse(capture.watcher.is_alive())

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is not installed')
    def test_stop_event_ends_real_file_replay(self):
        source = Path(self.folder.name) / 'long.wav'
        with wave.open(str(source), 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(live.RATE)
            audio.writeframes(np.full(live.RATE * 10, 4096, dtype='<i2').tobytes())
        stop = threading.Event()
        capture = live.AudioCapture(source=source, stop=stop, seconds=2)
        try:
            stop.set()
            self.assertTrue(capture.finished.wait(timeout=10))
            self.assertIsNone(capture.error)
        finally:
            capture.close()
        self.assertIsNotNone(capture.process.poll())
        self.assertFalse(capture.thread.is_alive())
        self.assertFalse(capture.watcher.is_alive())


if __name__=='__main__': unittest.main()
