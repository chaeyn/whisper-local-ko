"""Real FFmpeg/model tests. Set WHISPER_INTEGRATION=1 to enable them."""
import os
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(os.getenv('WHISPER_INTEGRATION') == '1', 'Set WHISPER_INTEGRATION=1 for real model tests')
class InferenceTests(unittest.TestCase):
    def test_file_transcription_and_live_replay_save_korean(self):
        from whisper_m4a import transcribe_file
        from whisper_live import run_live
        source = Path(__file__).parent / 'fixtures' / 'korean-greeting.ogg'
        with tempfile.TemporaryDirectory(prefix='whisper 한국어 ') as folder:
            output = Path(folder) / 'result.ko.txt'
            text, saved = transcribe_file(source, model_size='tiny', language='ko', output=output)
            self.assertEqual(saved.read_text(encoding='utf-8').strip(), text)
            self.assertRegex(text, '[가-힣]')
            self.assertIn('안녕', text)
            events = []
            live_output = Path(folder) / 'live.ko.txt'
            transcript, _ = run_live(live_output, source=source, seconds=2,
                                     emit=lambda *event: events.append(event))
            self.assertRegex(transcript, '[가-힣]')
            self.assertEqual(live_output.read_text(encoding='utf-8').strip(), transcript)
            self.assertTrue(any(kind == 'caption' for kind, _ in events))


if __name__ == '__main__':
    unittest.main()
