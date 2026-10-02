import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import whisper_m4a as app


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.audio = Path(self.folder.name) / '회의.m4a'
        self.audio.write_bytes(b'fixture')

    def run_conversion(self, language, text):
        model = Mock()
        model.transcribe.return_value = {'language': language, 'text': text}
        whisper = Mock()
        whisper.load_model.return_value = model
        with patch.dict('sys.modules', {'whisper': whisper}), patch.object(app.shutil, 'which', return_value='/ffmpeg'):
            return app.transcribe_file(self.audio, status=lambda _: None)

    def test_korean_utf8_and_existing_result_protected(self):
        text, output = self.run_conversion('ko', ' 안녕하세요 ')
        self.assertEqual(text, '안녕하세요')
        self.assertEqual(output.read_text(), '안녕하세요\n')
        with self.assertRaises(FileExistsError):
            self.run_conversion('ko', '교체')
        self.assertEqual(output.read_text(), '안녕하세요\n')

    def test_english_uses_local_translation(self):
        with patch.object(app, 'EnglishToKoreanTranslator') as translator:
            translator.return_value.translate.return_value = '안녕하세요'
            text, output = self.run_conversion('en', 'Hello')
            translator.return_value.translate.assert_called_once_with('Hello')
            self.assertEqual(output.read_text(), text + '\n')

    def test_unsupported_and_empty_do_not_save(self):
        for language, text in [('ja', 'こんにちは'), ('ko', '')]:
            with self.assertRaises(ValueError):
                self.run_conversion(language, text)
            self.assertFalse(self.audio.with_suffix('.ko.txt').exists())

    def test_output_cannot_replace_source(self):
        with self.assertRaises(ValueError):
            app.transcribe_file(self.audio, output=self.audio, overwrite=True)
        self.assertEqual(self.audio.read_bytes(), b'fixture')

    def test_overwrite_and_blank_preserve_existing(self):
        output = self.audio.with_suffix('.ko.txt')
        output.write_text('기존')
        with self.assertRaises(ValueError):
            app.save_transcript(output, '', overwrite=True)
        self.assertEqual(output.read_text(), '기존')
        app.save_transcript(output, '새 결과', overwrite=True)
        self.assertEqual(output.read_text(), '새 결과\n')
        self.assertFalse(list(output.parent.glob('.whisper-*')))

    def test_public_translation_model_ignores_inherited_credentials(self):
        transformers = Mock()
        with patch.dict('sys.modules', {'transformers': transformers}):
            app.EnglishToKoreanTranslator()
        transformers.MarianTokenizer.from_pretrained.assert_called_once_with(app.TRANSLATION_MODEL, revision=app.TRANSLATION_REVISION, token=False)
        transformers.MarianMTModel.from_pretrained.assert_called_once_with(app.TRANSLATION_MODEL, revision=app.TRANSLATION_REVISION, token=False)

    def test_long_translation_chunks_keep_all_tokens(self):
        translator = object.__new__(app.EnglishToKoreanTranslator)
        translator.tokenizer = Mock()
        translator.tokenizer.encode.side_effect = lambda text, **_: list(map(int, text.split()))
        translator.tokenizer.decode.side_effect = lambda ids, **_: ' '.join(map(str, ids))
        original = list(range(1100))
        chunks = translator._split_into_chunks(' '.join(map(str, original)))
        recovered = [int(token) for chunk in chunks for token in chunk.split()]
        self.assertEqual(original, recovered)
        self.assertTrue(all(len(chunk.split()) <= 400 for chunk in chunks))


if __name__ == '__main__':
    unittest.main()
