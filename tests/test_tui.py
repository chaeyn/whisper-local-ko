import curses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from whisper_tui import Tui, parse_path, wrap_cells, convert_worker, progress_bar


class TuiTests(unittest.TestCase):
    def setUp(self):
        self.context = Mock()
        self.patcher = patch('whisper_tui.mp.get_context', return_value=self.context)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.ui = Tui(Mock())
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.source = (Path(self.folder.name) / '회의 녹음.m4a').resolve()
        self.source.write_bytes(b'fixture')
        self.ui.fields[0] = str(self.source)

    def test_path_input_handles_quotes_spaces_and_home(self):
        self.assertEqual(parse_path(f'"{self.source}"'), self.source)
        self.assertEqual(parse_path(str(self.source)), self.source)
        self.assertEqual(parse_path(str(self.source).replace(' ', '\\ ')), self.source)
        self.assertEqual(parse_path('~/file.m4a'), Path.home() / 'file.m4a')

    def test_existing_output_requires_confirmation(self):
        output = self.source.with_suffix('.ko.txt')
        output.write_text('기존')
        with patch.object(self.ui, 'launch') as launch:
            self.ui.start()
            self.assertEqual(self.ui.confirm, 'overwrite')
            launch.assert_not_called()
            self.ui.key('n')
            launch.assert_not_called()
            self.ui.start()
            self.ui.key('y')
            launch.assert_called_once_with(True)
        self.assertEqual(output.read_text(), '기존')

    def test_missing_file_can_retry(self):
        self.ui.fields[0] = str(self.source.parent / 'missing.m4a')
        self.ui.start()
        self.assertTrue(self.ui.status.startswith('Error:'))
        self.ui.fields[0] = str(self.source)
        with patch.object(self.ui, 'launch') as launch:
            self.ui.key('s')
            launch.assert_called_once_with(False)

    def test_busy_locks_settings_and_quit_requires_confirmation(self):
        self.ui.process = Mock()
        self.ui.key('m'); self.ui.key('l'); self.ui.key('f'); self.ui.key('s')
        self.assertEqual(self.ui.model, 2)
        self.assertEqual(self.ui.language, 0)
        self.assertFalse(self.ui.editing)
        self.ui.key('q')
        self.assertTrue(self.ui.running)
        self.ui.key('n')
        self.assertTrue(self.ui.running)
        self.ui.key('q'); self.ui.key('y')
        self.assertFalse(self.ui.running)

    def test_input_accepts_unicode_and_clear(self):
        self.ui.key('f'); self.ui.key('\x15')
        for char in '한글 파일.m4a': self.ui.key(char)
        self.ui.key('\n')
        self.assertFalse(self.ui.editing)
        self.assertEqual(self.ui.fields[0], '한글 파일.m4a')

    def test_result_wrapping_and_scroll(self):
        self.assertEqual(wrap_cells('가나다\n\nabc', 4), ['가나', '다', '', 'abc'])
        self.ui.key(curses.KEY_NPAGE)
        self.assertEqual(self.ui.scroll, 10)
        self.ui.key(curses.KEY_PPAGE)
        self.assertEqual(self.ui.scroll, 0)

    def test_worker_reports_success_and_errors(self):
        events = Mock()
        with patch('whisper_m4a.transcribe_file', return_value=('한국어', Path('result.txt'))) as convert:
            convert_worker(events, str(self.source), 'tiny', 'en', 'result.txt', False)
            self.assertEqual(convert.call_args.args[:3], (self.source, 'tiny', 'en'))
            events.put.assert_called_with(('success', ('한국어', 'result.txt')))
        with patch('whisper_m4a.transcribe_file', side_effect=ValueError('파일 오류')):
            convert_worker(events, str(self.source), 'tiny', 'en', 'result.txt', False)
            events.put.assert_called_with(('error', '파일 오류'))

    def test_stop_reaps_worker_and_replaces_queue(self):
        process = self.ui.process = Mock()
        events = self.ui.events
        self.ui.stop_worker()
        process.terminate.assert_called_once()
        process.join.assert_called_once()
        process.close.assert_called_once()
        events.close.assert_called_once()
        self.assertIsNone(self.ui.process)

    def test_original_output_is_rejected(self):
        self.ui.fields[1] = str(self.source)
        self.ui.start()
        self.assertTrue(self.ui.status.startswith('Error:'))
        self.context.Process.assert_not_called()

    def test_browser_filters_audio_and_selects_file(self):
        (self.source.parent / 'notes.txt').write_text('내용')
        self.ui.key('b')
        self.assertTrue(self.ui.browsing)
        self.assertNotIn('notes.txt', [entry.name for entry in self.ui.entries])
        self.ui.selection = self.ui.entries.index(self.source)
        self.ui.key('\n')
        self.assertFalse(self.ui.browsing)
        self.assertEqual(self.ui.fields[0], str(self.source))

    def test_browser_enters_folder_and_cancel_preserves_file(self):
        folder = self.source.parent / '오디오'
        folder.mkdir()
        self.ui.key('b')
        self.ui.selection = self.ui.entries.index(folder)
        self.ui.key('\n')
        self.assertEqual(self.ui.directory, folder)
        self.ui.key(curses.KEY_BACKSPACE)
        self.assertEqual(self.ui.directory, folder.parent)
        self.ui.key('\x1b')
        self.assertEqual(self.ui.fields[0], str(self.source))

    def test_browser_is_locked_during_conversion(self):
        self.ui.process = Mock()
        self.ui.key('b')
        self.assertFalse(self.ui.browsing)

    def test_progress_bar_reports_measured_stage_fraction(self):
        self.assertIn('50%', progress_bar(('Transcribing', 50, 100)))
        self.assertIn('100%', progress_bar(('Done', 1, 1)))
        loading = progress_bar(('Loading Whisper', None, None), busy=True)
        self.assertIn('>>>', loading)
        self.assertNotIn('%', loading)

    def test_draw_handles_small_and_large_terminals(self):
        for dimensions in [(8, 25), (24, 80), (40, 120)]:
            self.ui.screen.getmaxyx.return_value = dimensions
            self.ui.draw()
        self.ui.screen.refresh.assert_called()


if __name__ == '__main__':
    unittest.main()
