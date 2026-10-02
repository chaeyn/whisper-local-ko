import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from filelock import FileLock, Timeout

import whisper_platform as platform_support


class PlatformTests(unittest.TestCase):
    def test_model_lock_uses_shared_cache_and_blocks_a_second_writer(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"XDG_CACHE_HOME": folder}):
            with platform_support.model_download_lock("tiny") as cache:
                self.assertEqual(cache, Path(folder) / "whisper")
                lock = FileLock(cache / ".tiny.download.lock", timeout=0)
                with self.assertRaises(Timeout):
                    lock.acquire()
            with lock:
                self.assertTrue(lock.is_locked)

    def test_model_lock_releases_after_failed_download(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"XDG_CACHE_HOME": folder}):
            with self.assertRaisesRegex(RuntimeError, "Download failed"):
                with platform_support.model_download_lock("tiny"):
                    raise RuntimeError("Download failed")
            with FileLock(Path(folder) / "whisper" / ".tiny.download.lock", timeout=0):
                pass

    def test_model_lock_rejects_path_components(self):
        with self.assertRaises(ValueError):
            with platform_support.model_download_lock("../tiny"):
                self.fail("Invalid model name was accepted")

    def test_macos_audio_input_disables_video(self):
        self.assertEqual(platform_support.audio_input_arguments("1", "Darwin"),
                         ["-f", "avfoundation", "-i", "none:1"])

    def test_linux_audio_input_accepts_default_and_named_sources(self):
        for name in ("default", "alsa_input.usb_Microphone"):
            self.assertEqual(platform_support.audio_input_arguments(name, "Linux"),
                             ["-f", "pulse", "-i", name])

    def test_windows_default_resolves_first_audio_device(self):
        with patch.object(platform_support, "audio_devices", return_value=[("USB Microphone", "USB Microphone")]):
            self.assertEqual(platform_support.audio_input_arguments("default", "Windows"),
                             ["-f", "dshow", "-i", "audio=USB Microphone"])

    def test_windows_explicit_name_preserves_spaces_and_unicode(self):
        name = "마이크 (USB Audio)"
        self.assertEqual(platform_support.audio_input_arguments(name, "Windows"),
                         ["-f", "dshow", "-i", f"audio={name}"])

    def test_windows_name_with_colon_resolves_alternative_id(self):
        devices = [("@device_cm_{id}", "Line: Input")]
        with patch.object(platform_support, "audio_devices", return_value=devices):
            self.assertEqual(platform_support.audio_input_arguments("Line: Input", "Windows")[-1],
                             "audio=@device_cm_{id}")

    def test_unsupported_microphone_system_has_clear_error(self):
        with self.assertRaisesRegex(RuntimeError, "not supported on FreeBSD"):
            platform_support.audio_input_arguments(system="FreeBSD")

    def list_devices(self, system, stderr="", stdout=""):
        result = Mock(stderr=stderr, stdout=stdout, returncode=1)
        with patch.object(platform_support.subprocess, "run", return_value=result) as run:
            devices = platform_support.audio_devices(system)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        return devices, run.call_args.args[0]

    def test_macos_listing_excludes_video_inputs(self):
        text = ('[AVFoundation @ 0x1] AVFoundation video devices:\n'
                '[AVFoundation @ 0x1] [0] Camera\n'
                '[AVFoundation @ 0x1] AVFoundation audio devices:\n'
                '[AVFoundation @ 0x1] [0] USB Microphone\n'
                '[AVFoundation @ 0x1] [1] Built-in Microphone\n'
                'Error opening input file .')
        devices, command = self.list_devices("Darwin", stderr=text)
        self.assertEqual(devices, [("0", "USB Microphone"), ("1", "Built-in Microphone")])
        self.assertEqual(command[-2:], ["-i", ""])

    def test_windows_listing_excludes_video_and_alternative_name_rows(self):
        text = ('[dshow @ 0x1] "Camera" (video)\n'
                '[dshow @ 0x1]   Alternative name "@camera"\n'
                '[dshow @ 0x1] "USB Microphone" (audio)\n'
                '[dshow @ 0x1]   Alternative name "@microphone"\n')
        devices, command = self.list_devices("Windows", stderr=text)
        self.assertEqual(devices, [("USB Microphone", "USB Microphone")])
        self.assertIn("dshow", command)

    def test_windows_duplicate_and_colon_names_use_unique_ids(self):
        text = ('[dshow @ 0x1] "USB Microphone" (audio)\n'
                '[dshow @ 0x1]   Alternative name "@mic1"\n'
                '[dshow @ 0x1] "USB Microphone" (audio)\n'
                '[dshow @ 0x1]   Alternative name "@mic2"\n'
                '[dshow @ 0x1] "Line: Input" (audio)\n'
                '[dshow @ 0x1]   Alternative name "@line"\n')
        devices, _ = self.list_devices("Windows", stderr=text)
        self.assertEqual(devices, [("@mic1", "USB Microphone"), ("@mic2", "USB Microphone"), ("@line", "Line: Input")])

    def test_windows_legacy_listing_reads_audio_section(self):
        text = ('[dshow @ 0x1] DirectShow video devices\n'
                '[dshow @ 0x1] "Camera"\n'
                '[dshow @ 0x1] DirectShow audio devices\n'
                '[dshow @ 0x1] "Microphone"\n'
                '[dshow @ 0x1]   Alternative name "@microphone"\n')
        devices, _ = self.list_devices("Windows", stderr=text)
        self.assertEqual(devices, [("Microphone", "Microphone")])

    def test_linux_listing_reads_source_names_and_descriptions(self):
        text = ('Auto-detected sources for pulse:\n'
                '* alsa_input.usb_Mic [USB Microphone] (audio)\n'
                '  alsa_output.pci.monitor [Monitor of Built-in Audio] (none)\n')
        devices, command = self.list_devices("Linux", stdout=text)
        self.assertEqual(devices, [("alsa_input.usb_Mic", "USB Microphone"),
                                  ("alsa_output.pci.monitor", "Monitor of Built-in Audio")])
        self.assertEqual(command[-2:], ["-sources", "pulse"])

    def test_no_devices_and_missing_backends_return_actionable_errors(self):
        for system, backend in (("Darwin", "avfoundation"), ("Windows", "dshow"), ("Linux", "pulse")):
            with self.subTest(system=system):
                with patch.object(platform_support.subprocess, "run", return_value=Mock(stdout="", stderr="Unknown input format")):
                    with self.assertRaisesRegex(RuntimeError, f"FFmpeg must support {backend}"):
                        platform_support.audio_devices(system)

    def test_device_lookup_handles_missing_ffmpeg(self):
        with patch.object(platform_support.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(RuntimeError, "Install FFmpeg"):
                platform_support.audio_devices("Linux")

    def test_device_lookup_handles_timeout(self):
        with patch.object(platform_support.subprocess, "run", side_effect=subprocess.TimeoutExpired("ffmpeg", 15)):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                platform_support.audio_devices("Windows")


if __name__ == "__main__":
    unittest.main()
