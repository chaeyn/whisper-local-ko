"""Validate the standalone release installer without fetching or installing packages."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "install.sh").read_text(encoding="utf-8")
PYTHON_SOURCE = SCRIPT.split("<<'WHISPER_INSTALL_PY'\n", 1)[1].rsplit("\nWHISPER_INSTALL_PY", 1)[0]
installer = types.ModuleType("release_installer")
exec(compile(PYTHON_SOURCE, str(ROOT / "install.sh"), "exec"), installer.__dict__)


class ReleaseFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="whisper release '")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.archive = self.root / installer.ARCHIVE
        self.sums = self.root / "SHA256SUMS.txt"
        self.prefix = self.root / "data ' directory"
        self.bin = self.root / "bin ' directory"
        self.setup_log = self.root / "setup.log"
        self.run_log = self.root / "run.json"
        self.environment = mock.patch.dict(os.environ, {
            "WHISPER_TEST_SETUP_LOG": str(self.setup_log),
            "WHISPER_TEST_RUN_LOG": str(self.run_log),
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def make_archive(self, extra=(), setup_exit=0):
        setup = f'#!/bin/sh\nprintf setup > "$WHISPER_TEST_SETUP_LOG"\nexit {setup_exit}\n'
        run_python = (
            "import json, os, sys\n"
            "with open(os.environ['WHISPER_TEST_RUN_LOG'], 'w') as output:\n"
            "    json.dump({'args': sys.argv[1:], 'cwd': os.getcwd(), 'tty': os.isatty(0)}, output)\n"
        )
        run = f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$(dirname "$0")/fake_app.py" "$@"\n'
        entries = [("scripts/setup.sh", setup.encode()), ("scripts/run.sh", run.encode()),
                   ("scripts/fake_app.py", run_python.encode()), ("pyproject.toml", b"# test fixture\n")]
        with tarfile.open(self.archive, "w:gz") as output:
            for name, content in entries:
                member = tarfile.TarInfo(f"{installer.ARCHIVE_ROOT}/{name}")
                member.size = len(content)
                output.addfile(member, io.BytesIO(content))
            for member, content in extra:
                output.addfile(member, io.BytesIO(content) if content else None)
        self.sums.write_text(f"{hashlib.sha256(self.archive.read_bytes()).hexdigest()}  {installer.ARCHIVE}\n")

    def local_download(self, url, target, limit=installer.MAX_DOWNLOAD):
        source = self.sums if url.endswith("/SHA256SUMS.txt") else self.archive
        shutil.copyfile(source, target)

    def perform_install(self):
        with mock.patch.object(installer, "download", self.local_download), redirect_stdout(io.StringIO()):
            return installer.install(self.prefix, self.bin)


class ArchiveTests(ReleaseFixture):
    def test_checksum_mismatch_missing_and_duplicate_entries_are_rejected(self):
        self.make_archive()
        valid = self.sums.read_text()
        for content in ("0" * 64 + f"  {installer.ARCHIVE}\n", "", valid + valid,
                        "g" * 64 + f"  {installer.ARCHIVE}\n"):
            with self.subTest(content=content):
                self.sums.write_text(content)
                with self.assertRaises(installer.InstallError):
                    installer.verify_archive(self.archive, self.sums)
        self.sums.write_text(valid)
        installer.verify_archive(self.archive, self.sums)

    def test_safe_archive_extracts_required_files_without_setuid_permissions(self):
        member = tarfile.TarInfo(f"{installer.ARCHIVE_ROOT}/extra.sh")
        member.mode = 0o6777
        member.size = 4
        self.make_archive([(member, b"exit")])
        destination = self.root / "extracted"
        project = installer.extract_archive(self.archive, destination)
        self.assertEqual(project, destination / installer.ARCHIVE_ROOT)
        self.assertEqual((project / "extra.sh").read_bytes(), b"exit")
        if os.name != "nt":
            self.assertEqual((project / "extra.sh").stat().st_mode & 0o7777, 0o755)

    def test_traversal_absolute_foreign_root_and_links_are_rejected_before_writes(self):
        unsafe = [
            (f"{installer.ARCHIVE_ROOT}/../../escaped", tarfile.REGTYPE),
            ("/tmp/escaped", tarfile.REGTYPE),
            ("another-project/scripts/setup.sh", tarfile.REGTYPE),
            (f"{installer.ARCHIVE_ROOT}/..\\escaped", tarfile.REGTYPE),
            (f"{installer.ARCHIVE_ROOT}/linked", tarfile.SYMTYPE),
            (f"{installer.ARCHIVE_ROOT}/linked", tarfile.LNKTYPE),
            (f"{installer.ARCHIVE_ROOT}/device", tarfile.CHRTYPE),
            (f"{installer.ARCHIVE_ROOT}/fifo", tarfile.FIFOTYPE),
            (f"{installer.ARCHIVE_ROOT}/scripts/setup.sh", tarfile.REGTYPE),
        ]
        for name, kind in unsafe:
            with self.subTest(name=name, kind=kind):
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = "../../outside"
                self.make_archive([(member, b"")])
                destination = self.root / "extracted"
                with self.assertRaises(installer.InstallError):
                    installer.extract_archive(self.archive, destination)
                self.assertFalse(destination.exists())

    def test_extraction_size_limit_prevents_writes(self):
        self.make_archive()
        with mock.patch.object(installer, "MAX_EXTRACT", 1), self.assertRaises(installer.InstallError):
            installer.extract_archive(self.archive, self.root / "extracted")
        self.assertFalse((self.root / "extracted").exists())

    def test_download_rejects_http_and_https_redirect_to_http(self):
        with self.assertRaises(installer.InstallError):
            installer.download("http://example.invalid/release", self.root / "download")
        request = installer.urllib.request.Request("https://example.invalid/release")
        with self.assertRaises(installer.InstallError):
            installer.HTTPSRedirect().redirect_request(request, None, 302, "", {}, "http://example.invalid/data")

    def test_https_download_obeys_size_limit(self):
        response = io.BytesIO(b"release contents")
        response.geturl = lambda: "https://release-assets.githubusercontent.com/asset"
        opener = mock.Mock()
        opener.open.return_value = response
        target = self.root / "download"
        with mock.patch.object(installer.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(installer.InstallError):
                installer.download("https://github.com/example/release", target, limit=2)
        self.assertEqual(target.read_bytes(), b"")


@unittest.skipIf(os.name == "nt", "The release shell installer targets macOS and Linux")
class InstallationTests(ReleaseFixture):
    def test_success_publishes_launcher_with_quoted_paths_and_forwards_arguments(self):
        self.make_archive()
        launcher = self.perform_install()
        self.assertEqual(launcher, self.bin / "whisper-ko")
        self.assertEqual(self.setup_log.read_text(), "setup")
        self.assertFalse(self.run_log.exists())
        arguments = ["transcribe", "recording ' with spaces.mp3", "--output", "한글.txt", ""]
        result = subprocess.run([str(launcher), *arguments], cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.run_log.read_text())["args"], arguments)
        self.assertEqual(json.loads(self.run_log.read_text())["cwd"], str(self.root))
        releases = list((self.prefix / "releases").iterdir())
        self.assertEqual(len(releases), 1)
        self.assertIn(str(releases[0]), launcher.read_text().replace("'\"'\"'", "'"))

    def test_reinstall_preserves_previous_release_and_updates_launcher(self):
        self.make_archive()
        launcher = self.perform_install()
        previous = launcher.read_bytes()
        first_release, = (self.prefix / "releases").iterdir()
        self.perform_install()
        self.assertNotEqual(launcher.read_bytes(), previous)
        self.assertTrue(first_release.is_dir())
        self.assertEqual(len(list((self.prefix / "releases").iterdir())), 2)

    def test_setup_failure_keeps_previous_launcher_and_removes_new_release(self):
        self.make_archive()
        launcher = self.perform_install()
        previous = launcher.read_bytes()
        old_releases = list((self.prefix / "releases").iterdir())
        self.make_archive(setup_exit=17)
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.perform_install()
        self.assertEqual(failure.exception.returncode, 17)
        self.assertEqual(launcher.read_bytes(), previous)
        self.assertEqual(list((self.prefix / "releases").iterdir()), old_releases)

    def test_failed_checksum_never_runs_setup_or_publishes_launcher(self):
        self.make_archive()
        self.sums.write_text("0" * 64 + f"  {installer.ARCHIVE}\n")
        with self.assertRaises(installer.InstallError):
            self.perform_install()
        self.assertFalse(self.setup_log.exists())
        self.assertFalse((self.bin / "whisper-ko").exists())
        self.assertEqual(list((self.prefix / "releases").iterdir()), [])

    def test_unrelated_file_directory_and_symlink_are_preserved_before_download(self):
        self.bin.mkdir()
        launcher = self.bin / "whisper-ko"
        for kind in ("file", "directory", "symlink"):
            with self.subTest(kind=kind):
                if kind == "file":
                    launcher.write_text("user-owned command")
                elif kind == "directory":
                    launcher.mkdir()
                else:
                    launcher.symlink_to(self.root / "missing-target")
                with mock.patch.object(installer, "download") as fetch:
                    with self.assertRaises(installer.InstallError):
                        installer.install(self.prefix, self.bin)
                    fetch.assert_not_called()
                self.assertTrue(os.path.lexists(launcher))
                if kind == "directory":
                    launcher.rmdir()
                else:
                    launcher.unlink()

    def test_changed_launcher_is_preserved(self):
        self.make_archive()
        launcher = self.perform_install()
        expected = installer.launcher_state(launcher)
        launcher.write_text("a user replacement")
        with self.assertRaises(installer.InstallError):
            installer.publish_launcher(launcher, self.root / "project", expected)
        self.assertEqual(launcher.read_text(), "a user replacement")
        self.assertEqual(list(self.bin.glob(".whisper-ko-*")), [])

    def test_concurrent_installation_is_rejected(self):
        self.bin.mkdir()
        with installer.installation_lock(self.bin):
            with self.assertRaisesRegex(installer.InstallError, "Another installation"):
                with installer.installation_lock(self.bin):
                    self.fail("A second installer acquired the same lock")

    def test_run_without_terminal_keeps_completed_install(self):
        self.make_archive()
        with mock.patch.object(installer, "download", self.local_download), \
                mock.patch.object(installer.platform, "system", return_value="Linux"), \
                mock.patch.object(installer.platform, "machine", return_value="x86_64"), \
                mock.patch.object(installer.shutil, "which", return_value="/usr/bin/ffmpeg"), \
                redirect_stdout(io.StringIO()):
            original_open = os.open

            def no_terminal(path, *args, **kwargs):
                if str(path) == "/dev/tty":
                    raise OSError("no controlling terminal")
                return original_open(path, *args, **kwargs)

            with mock.patch.object(installer.os, "open", side_effect=no_terminal):
                with self.assertRaisesRegex(installer.InstallError, "Installation is complete"):
                    installer.main(["--run", "--prefix", str(self.prefix), "--bin-dir", str(self.bin)])
        self.assertTrue((self.bin / "whisper-ko").is_file())
        self.assertEqual(len(list((self.prefix / "releases").iterdir())), 1)


@unittest.skipIf(os.name == "nt", "The release shell installer targets macOS and Linux")
class ShellBootstrapTests(ReleaseFixture):
    def setUp(self):
        super().setUp()
        self.programs = self.root / "programs"
        self.programs.mkdir()
        self.fake_program("ffmpeg", "exit 0")
        self.fake_program("brew", "exit 1")
        self.env = dict(os.environ, WHISPER_PYTHON=sys.executable,
                        PATH=f"{self.programs}:/usr/bin:/bin")

    def fake_program(self, name, body):
        path = self.programs / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
        return path

    def fixture_script(self):
        # Inject a trusted local downloader into a temporary test copy only.
        # Production has no URL, checksum, or validation bypass switch.
        replacement = (
            "def fixture_download(url, target, limit=MAX_DOWNLOAD):\n"
            f"    folder = Path({str(self.root)!r})\n"
            "    source = folder / ('SHA256SUMS.txt' if url.endswith('/SHA256SUMS.txt') else ARCHIVE)\n"
            "    shutil.copyfile(source, target)\n"
            "download = fixture_download\n\n"
        )
        script = self.root / "test installer.sh"
        script.write_text(SCRIPT.replace('if __name__ == "__main__":', replacement + 'if __name__ == "__main__":'))
        return script

    def test_help_does_not_require_python_or_touch_install_paths(self):
        for shell in dict.fromkeys(["/bin/sh", shutil.which("dash")]):
            if not shell:
                continue
            result = subprocess.run([shell, str(ROOT / "install.sh"), "--help"],
                                    env=dict(self.env, WHISPER_PYTHON="missing-python"),
                                    text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Git is not required", result.stdout)
        self.assertFalse(self.prefix.exists())

    def test_invalid_explicit_python_stops_before_download(self):
        result = subprocess.run(["/bin/sh", str(ROOT / "install.sh")],
                                env=dict(self.env, WHISPER_PYTHON="missing-python"),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("WHISPER_PYTHON must select", result.stderr)

    def test_optimized_python_still_rejects_unsupported_version(self):
        helper = self.root / "unsupported python.py"
        helper.write_text(
            "import sys\n"
            "if sys.argv[1:2] != ['-c']:\n"
            "    raise SystemExit(99)\n"
            "sys.version_info = (3, 14, 0)\n"
            "exec(compile(sys.argv[2], '<version check>', 'exec'))\n"
        )
        candidate = self.fake_program("unsupported-python", f'exec {shlex.quote(sys.executable)} {shlex.quote(str(helper))} "$@"')
        result = subprocess.run(["/bin/sh", str(ROOT / "install.sh")],
                                env=dict(self.env, WHISPER_PYTHON=str(candidate), PYTHONOPTIMIZE="1"),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("WHISPER_PYTHON must select", result.stderr)

    def test_pipe_install_works_with_sh_and_dash_without_running_app(self):
        self.make_archive()
        script = self.fixture_script().read_text()
        for shell in dict.fromkeys(["/bin/sh", shutil.which("dash")]):
            if not shell:
                continue
            with self.subTest(shell=shell):
                result = subprocess.run([shell, "-s", "--", "--prefix", str(self.prefix), "--bin-dir", str(self.bin)],
                                        input=script, env=self.env, text=True, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((self.bin / "whisper-ko").is_file())
                self.assertFalse(self.run_log.exists())

    def test_versioned_python_fallback_finds_supported_interpreter(self):
        self.make_archive()
        self.fake_program("python3.12", "exit 1")
        self.fake_program("python3.11", f'exec {shlex.quote(sys.executable)} "$@"')
        self.fake_program("python3", "exit 1")
        environment = dict(self.env)
        environment.pop("WHISPER_PYTHON", None)
        result = subprocess.run(["/bin/sh", str(self.fixture_script()), "--prefix", str(self.prefix), "--bin-dir", str(self.bin)],
                                env=environment, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.bin / "whisper-ko").is_file())

    def test_pipe_run_restores_controlling_terminal_for_app(self):
        import pty
        import select
        import time
        self.make_archive()
        script = self.fixture_script()
        command = (f"cat {shlex.quote(str(script))} | sh -s -- --run "
                   f"--prefix {shlex.quote(str(self.prefix))} --bin-dir {shlex.quote(str(self.bin))}")
        pid, terminal = pty.fork()
        if pid == 0:
            os.chdir(self.root)
            os.execve("/bin/sh", ["sh", "-c", command], self.env)
        output = bytearray()
        completed = False
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                ready, _, _ = select.select([terminal], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(terminal, 4096)
                    except OSError:
                        chunk = b""
                    if chunk:
                        output.extend(chunk)
                waited, status = os.waitpid(pid, os.WNOHANG)
                if waited:
                    completed = True
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0, output.decode(errors="replace"))
                    break
            self.assertTrue(completed, output.decode(errors="replace"))
        finally:
            os.close(terminal)
            if not completed:
                import signal
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
        event = json.loads(self.run_log.read_text())
        self.assertTrue(event["tty"], "A piped installer must not pass its exhausted stdin pipe to curses")
        self.assertEqual(event["cwd"], str(self.root))
        self.assertEqual(event["args"], [])


if __name__ == "__main__":
    unittest.main()
