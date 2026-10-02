import contextlib
import errno
import io
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
        with patch.dict('sys.modules', {'whisper': whisper}), \
                patch.object(app.shutil, 'which', return_value='/ffmpeg'), \
                patch.object(app, 'model_download_lock', return_value=contextlib.nullcontext(Path(self.folder.name))):
            return app.transcribe_file(self.audio, status=lambda _: None)

    def test_korean_utf8_and_existing_result_protected(self):
        text, output = self.run_conversion('ko', ' 안녕하세요 ')
        self.assertEqual(text, '안녕하세요')
        self.assertEqual(output.read_text(encoding="utf-8"), '안녕하세요\n')
        with self.assertRaises(FileExistsError):
            self.run_conversion('ko', '교체')
        self.assertEqual(output.read_text(encoding="utf-8"), '안녕하세요\n')

    def test_english_uses_local_translation(self):
        with patch.object(app, 'EnglishToKoreanTranslator') as translator:
            translator.return_value.translate.return_value = '안녕하세요'
            text, output = self.run_conversion('en', 'Hello')
            translator.return_value.translate.assert_called_once_with('Hello')
            self.assertEqual(output.read_text(encoding="utf-8"), text + '\n')

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
        output.write_text('기존', encoding="utf-8")
        with self.assertRaises(ValueError):
            app.save_transcript(output, '', overwrite=True)
        self.assertEqual(output.read_text(encoding="utf-8"), '기존')
        app.save_transcript(output, '새 결과', overwrite=True)
        self.assertEqual(output.read_text(encoding="utf-8"), '새 결과\n')
        self.assertFalse(list(output.parent.glob('.whisper-*')))

    def test_failed_publish_removes_temporary_file(self):
        output = self.audio.with_suffix('.ko.txt')
        with patch.object(app.os, 'link', side_effect=OSError('저장 실패')):
            with self.assertRaises(OSError):
                app.save_transcript(output, '결과')
        self.assertFalse(output.exists())
        self.assertFalse(list(output.parent.glob('.whisper-*')))

    def test_unsupported_output_link_has_a_hint_and_preserves_source(self):
        output = self.audio.with_suffix(".ko.txt")
        for code in sorted({errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EPERM}):
            original = OSError(code, "Cannot create hard link")
            with self.subTest(errno=code), patch.object(app.os, "link", side_effect=original):
                with self.assertRaisesRegex(OSError, "Choose a writable local output folder") as result:
                    app.save_transcript(output, "결과")
            self.assertIs(result.exception.__cause__, original)
            self.assertEqual(self.audio.read_bytes(), b"fixture")
            self.assertFalse(output.exists())
            self.assertFalse(list(output.parent.glob(".whisper-*")))

    def test_windows_unsupported_link_has_a_hint(self):
        output = self.audio.with_suffix(".ko.txt")
        for code in (1, 50):
            original = OSError(errno.EINVAL, "Operation not supported")
            original.winerror = code
            with self.subTest(winerror=code), patch.object(app.os, "link", side_effect=original):
                with self.assertRaisesRegex(OSError, "supports hard links") as result:
                    app.save_transcript(output, "결과")
            self.assertIs(result.exception.__cause__, original)
            self.assertFalse(output.exists())
            self.assertFalse(list(output.parent.glob(".whisper-*")))

    def test_existing_result_keeps_exact_collision_error(self):
        output = self.audio.with_suffix(".ko.txt")
        output.write_text("기존 결과", encoding="utf-8")
        original = FileExistsError(errno.EEXIST, "File exists", str(output))
        with patch.object(app.os, "link", side_effect=original):
            with self.assertRaises(FileExistsError) as result:
                app.save_transcript(output, "새 결과")
        self.assertIs(result.exception, original)
        self.assertEqual(output.read_text(encoding="utf-8"), "기존 결과")
        self.assertFalse(list(output.parent.glob(".whisper-*")))

    def test_whisper_progress_tracks_disabled_bar_and_restores_hook(self):
        import importlib
        module = importlib.import_module('whisper.transcribe')
        original = module.tqdm
        events = []
        class Model:
            def transcribe(self, *args, **kwargs):
                with module.tqdm.tqdm(total=100, disable=True) as bar:
                    bar.update(40)
                    bar.update(60)
                return {'text': '한국어'}
        result = app.transcribe_with_progress(Model(), self.audio, 'ko', lambda *event: events.append(event))
        self.assertEqual([event[1] for event in events], [0, 40, 100])
        self.assertEqual(result['text'], '한국어')
        self.assertIs(module.tqdm, original)

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


    def test_missing_ffmpeg_does_not_load_a_model(self):
        with patch.object(app.shutil, "which", return_value=None), \
                patch.object(app, "model_download_lock") as lock:
            with self.assertRaisesRegex(RuntimeError, "FFmpeg is missing"):
                app.transcribe_file(self.audio)
            lock.assert_not_called()

    def test_output_folder_is_rejected_before_model_load(self):
        with patch.object(app, "model_download_lock") as lock:
            with self.assertRaisesRegex(ValueError, "output path is a folder"):
                app.transcribe_file(self.audio, output=self.audio.parent, overwrite=True)
            lock.assert_not_called()

    def test_publish_collision_keeps_an_existing_result(self):
        output = self.audio.with_suffix(".ko.txt")
        output.write_text("기존 결과", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            app.save_transcript(output, "새 결과")
        self.assertEqual(output.read_text(encoding="utf-8"), "기존 결과")
        self.assertFalse(list(output.parent.glob(".whisper-*")))

    def test_progress_hook_is_restored_after_model_failure(self):
        import importlib
        module = importlib.import_module("whisper.transcribe")
        original = module.tqdm
        model = Mock()
        model.transcribe.side_effect = RuntimeError("Inference failed")
        with self.assertRaisesRegex(RuntimeError, "Inference failed"):
            app.transcribe_with_progress(model, self.audio, "ko", Mock())
        self.assertIs(module.tqdm, original)

    def test_gui_worker_sends_results_through_queue(self):
        import queue
        gui = object.__new__(app.WhisperTranscriber)
        gui.events = queue.Queue()
        output = self.audio.with_suffix(".ko.txt")
        with patch.object(app, "transcribe_file", return_value=("한국어", output)):
            gui._transcribe(self.audio, "tiny", "ko", False)
        self.assertEqual(gui.events.get_nowait(), ("success", ("한국어", output)))


class CommandTests(unittest.TestCase):
    def test_default_command_opens_tui_without_tk(self):
        tui = Mock()
        with patch.dict("sys.modules", {"whisper_tui": tui, "tkinter": None}):
            self.assertEqual(app.main([]), 0)
        tui.main.assert_called_once_with()

    def test_transcribe_command_passes_options(self):
        with patch.object(app, "transcribe_file", return_value=("결과", Path("result.txt"))) as convert, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = app.main(["transcribe", "source.wav", "--model", "tiny", "--language", "ko",
                             "--output", "result.txt", "--overwrite"])
        self.assertEqual(code, 0)
        convert.assert_called_once_with(Path("source.wav"), "tiny", "ko", Path("result.txt"), True)
        self.assertIn("Saved: result.txt", output.getvalue())

    def test_cli_reports_failure_with_nonzero_status(self):
        with patch.object(app, "transcribe_file", side_effect=ValueError("Audio file not found")), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            code = app.main(["transcribe", "missing.wav"])
        self.assertEqual(code, 1)
        self.assertIn("Error: Audio file not found", errors.getvalue())

    def test_version_and_help_do_not_start_interfaces(self):
        for argument in ("--version", "--help"):
            with self.subTest(argument=argument), \
                    patch.dict("sys.modules", {"whisper_tui": None, "tkinter": None}), \
                    contextlib.redirect_stdout(io.StringIO()) as output, \
                    self.assertRaises(SystemExit) as result:
                app.main([argument])
            self.assertEqual(result.exception.code, 0)
            self.assertIn("whisper-ko", output.getvalue())

    def test_live_command_passes_options_and_reports_errors(self):
        live = Mock()
        with patch.dict("sys.modules", {"whisper_live": live}):
            self.assertEqual(app.main(["live", "--list-devices"]), 0)
            live.main.assert_called_once_with(["--list-devices"])
            live.main.side_effect = RuntimeError("No input device")
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(app.main(["live"]), 1)
        self.assertIn("Error: No input device", errors.getvalue())

    def test_doctor_flags_and_exit_status(self):
        with patch.object(app, "doctor", return_value=False) as check:
            self.assertEqual(app.main(["doctor", "--no-gui", "--tui"]), 1)
        check.assert_called_once_with(gui=False, tui=True)

    def test_headless_doctor_skips_tk_and_checks_tui(self):
        with patch.object(app.importlib, "import_module", return_value=Mock()) as imports, \
                patch.dict(app.sys.modules, {"transformers": Mock()}), \
                patch.object(app.shutil, "which", return_value="ffmpeg"), \
                patch.object(app.sys, "version_info", (3, 12, 0)), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(app.doctor(gui=False, tui=True))
        names = [call.args[0] for call in imports.call_args_list]
        self.assertNotIn("tkinter", names)
        self.assertIn("curses", names)
        self.assertIn("[OK] FFmpeg", output.getvalue())

    def test_doctor_reports_missing_dependency(self):
        def import_module(name):
            if name == "curses":
                raise ImportError("No module named curses")
            return Mock()
        with patch.object(app.importlib, "import_module", side_effect=import_module), \
                patch.dict(app.sys.modules, {"transformers": Mock()}), \
                patch.object(app.shutil, "which", return_value="ffmpeg"), \
                patch.object(app.sys, "version_info", (3, 11, 0)), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(app.doctor(gui=False, tui=True))
        self.assertIn("[FAIL] curses", output.getvalue())
        self.assertIn("windows-curses", output.getvalue())


if __name__ == '__main__':
    unittest.main()
