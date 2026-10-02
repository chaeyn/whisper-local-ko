import queue
import io
import tempfile
import threading
import unittest
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
        self.assertEqual(self.output.read_text(), result[0]+'\n')

    def test_existing_result_is_never_replaced(self):
        self.output.write_text('기존')
        with self.assertRaises(FileExistsError): self.run_stream()
        self.assertEqual(self.output.read_text(), '기존')
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
        self.assertIn('첫 문장', self.output.read_text())

    def test_english_translates_locally(self):
        self.model.transcribe.side_effect=[{'language':'en','text':'Hello'}]*2
        with patch('whisper_m4a.EnglishToKoreanTranslator') as translator:
            translator.return_value.translate.return_value='안녕하세요'
            result,events=self.run_stream(language='en')
            translator.assert_called_once()
            self.assertEqual(translator.return_value.translate.call_count,2)
        self.assertEqual(result[0], '안녕하세요\n안녕하세요')

    def test_device_listing_reads_audio_section_only(self):
        stderr='AVFoundation video devices:\n[0] Camera\nAVFoundation audio devices:\n[0] External mic\n[1] Built-in mic\nError opening input'
        with patch.object(live.subprocess, 'run', return_value=Mock(stderr=stderr)):
            self.assertEqual(live.audio_devices(), [('0','External mic'),('1','Built-in mic')])

    def test_backlog_limit_stops_capture_without_silent_loss(self):
        process = Mock()
        process.stdout = io.BytesIO(np.full(live.RATE * 2 * 7, 0.1, dtype='<f4').tobytes())
        process.poll.return_value = 0
        process.wait.return_value = 0
        with patch.object(live.subprocess, 'Popen', return_value=process):
            capture = live.AudioCapture(seconds=2)
            capture.thread.join(timeout=2)
            self.assertEqual(capture.chunks.qsize(), 5)
            self.assertIn('some audio was not processed', capture.error)
            capture.close()

    def test_invalid_chunk_length_rejected(self):
        with patch.dict('sys.modules', {'whisper': self.whisper}):
            with self.assertRaises(ValueError): live.run_live(self.output, seconds=0)
        self.whisper.load_model.assert_not_called()


if __name__=='__main__': unittest.main()
