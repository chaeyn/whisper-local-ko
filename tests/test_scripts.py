"""Exercise Unix entrypoints through real shells with isolated boundary programs."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELLS = list(dict.fromkeys(path for path in ("/bin/sh", shutil.which("dash")) if path))
FAKE_PYTHON = '''import json, os, pathlib, shutil, sys
invoked, *args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps({"args": args, "cwd": os.getcwd(),
                             "pythonpath": os.environ.get("PYTHONPATH")}) + "\\n")
if args[:1] == ["-c"]:
    if "version_info" in args[1] and "print" not in args[1]:
        if os.environ.get("FAKE_BAD_PYTHON") or (os.environ.get("FAKE_BAD_VENV") and ".venv" in invoked):
            sys.version_info = (3, 14, 0)
        exec(compile(args[1], "<version check>", "exec"))
    if "print" in args[1]:
        print("3.11")
elif args[:2] == ["-m", "venv"]:
    target = pathlib.Path(args[2]) / "bin" / "python"
    target.parent.mkdir(parents=True)
    shutil.copy2(invoked, target)
elif args[:2] == ["-m", "pip"]:
    sys.exit(int(os.environ.get("FAKE_PIP_EXIT", "0")))
elif args and args[0].endswith("whisper_m4a.py"):
    sys.exit(int(os.environ.get("FAKE_DOCTOR_EXIT", "0")) if "doctor" in args else 0)
else:
    sys.exit("Unexpected Python invocation")
'''


class PythonVersionGuardTests(unittest.TestCase):
    def test_all_install_guards_work_when_python_optimization_is_enabled(self):
        for name in ("install.sh", "scripts/setup.sh", "scripts/setup.ps1"):
            source = (ROOT / name).read_text(encoding="utf-8")
            guards = re.findall(r"-c '(import sys; [^']*version_info[^']*)'", source)
            self.assertTrue(guards, f"Missing Python compatibility check in {name}")
            for guard in guards:
                for minor, expected in ((10, 1), (11, 0), (12, 0), (13, 1), (14, 1)):
                    with self.subTest(script=name, python=f"3.{minor}"):
                        result = subprocess.run([sys.executable, "-O", "-c",
                                                 f"import sys; sys.version_info = (3, {minor}, 0); {guard}"],
                                                text=True, capture_output=True, timeout=10)
                        self.assertEqual(result.returncode, expected, result.stderr)


@unittest.skipIf(os.name == "nt", "Unix shell entrypoints; Windows uses PowerShell")
class ShellScriptTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="whisper shell ")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        self.caller = self.root / "caller with spaces"
        self.project = self.caller / "project with spaces"
        self.bin = self.root / "fake programs"
        for path in (self.project / "scripts", self.caller, self.bin):
            path.mkdir(parents=True, exist_ok=True)
        for name in ("setup.sh", "run.sh"):
            target = self.project / "scripts" / name
            shutil.copyfile(ROOT / "scripts" / name, target)
            target.chmod(0o644)
        self.log = self.root / "calls.jsonl"
        helper = self.root / "fake python.py"
        helper.write_text(FAKE_PYTHON, encoding="utf-8")
        self.python = self.bin / "python with spaces"
        self.program(self.python, f'exec {shlex.quote(sys.executable)} {shlex.quote(str(helper))} "$0" "$@"')
        self.program(self.bin / "ffmpeg", "exit 0")
        self.program(self.bin / "brew", 'test -n "${FAKE_TK_PREFIX:-}" || exit 1\nprintf "%s\\n" "$FAKE_TK_PREFIX"')
        self.program(self.bin / "uname", 'case "$1" in -s) echo Linux ;; -m) echo x86_64 ;; esac')
        self.env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin", WHISPER_PYTHON=str(self.python),
                        FAKE_LOG=str(self.log), CDPATH=str(self.caller))
        self.env.pop("PYTHONPATH", None)

    def program(self, path, body):
        path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        path.chmod(0o755)

    def make_venv(self):
        target = self.project / ".venv" / "bin" / "python"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.python, target)

    def invoke(self, shell, script, *args, **environment):
        self.log.unlink(missing_ok=True)
        entrypoint = (self.project / "scripts" / script).relative_to(self.caller)
        result = subprocess.run([shell, str(entrypoint), *args],
                                cwd=self.caller, env=dict(self.env, **environment),
                                text=True, capture_output=True, timeout=15)
        events = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, events

    def app_calls(self, events):
        return [event for event in events if event["args"] and event["args"][0].endswith("whisper_m4a.py")]

    def test_help_and_invalid_options_do_not_start_installation(self):
        for shell in SHELLS:
            for args, expected in ((["--help"], 0), (["-h"], 0), (["--unknown"], 2), (["--run", "extra"], 2)):
                with self.subTest(shell=shell, args=args):
                    result, events = self.invoke(shell, "setup.sh", *args, WHISPER_PYTHON="missing-python")
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertIn("Usage:", result.stdout + result.stderr)
                    self.assertEqual(events, [])

    def test_install_creates_environment_and_checks_without_launching(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, events = self.invoke(shell, "setup.sh")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((self.project / ".venv/bin/python").is_file())
                self.assertEqual([call["args"][1:] for call in self.app_calls(events)],
                                 [["doctor", "--no-gui", "--tui"]])
                self.assertTrue(all(Path(event["cwd"]) == self.project for event in events))
                self.assertIn("Installation complete", result.stdout)
                shutil.rmtree(self.project / ".venv")

    def test_run_option_launches_after_successful_check(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, events = self.invoke(shell, "setup.sh", "--run")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([call["args"][1:] for call in self.app_calls(events)],
                                 [["doctor", "--no-gui", "--tui"], []])

    def test_runner_preserves_caller_directory_arguments_and_pythonpath(self):
        self.make_venv()
        tk = self.root / "Tk with spaces"
        (tk / "libexec").mkdir(parents=True)
        args = ["transcribe", "audio with spaces.mp3", "--output", "한글 result.txt", ""]
        for shell in SHELLS:
            for inherited in (None, "existing modules"):
                with self.subTest(shell=shell, pythonpath=inherited):
                    extra = {"FAKE_TK_PREFIX": str(tk)}
                    if inherited is not None:
                        extra["PYTHONPATH"] = inherited
                    result, events = self.invoke(shell, "run.sh", *args, **extra)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    call, = self.app_calls(events)
                    self.assertEqual(call["args"][1:], args)
                    self.assertEqual(Path(call["cwd"]), self.caller)
                    self.assertEqual(call["pythonpath"], str(tk / "libexec") + (":" + inherited if inherited else ""))

    def test_missing_or_incompatible_environment_stops_with_instructions(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result, events = self.invoke(shell, "run.sh")
                self.assertEqual(result.returncode, 1)
                self.assertIn("sh scripts/setup.sh", result.stderr)
                self.assertEqual(events, [])
                self.make_venv()
                result, events = self.invoke(shell, "setup.sh", FAKE_BAD_VENV="1")
                self.assertEqual(result.returncode, 1)
                self.assertIn("incompatible", result.stderr)
                self.assertEqual(self.app_calls(events), [])
                self.assertFalse(any(event["args"][:2] == ["-m", "pip"] for event in events))
                shutil.rmtree(self.project / ".venv")

    def test_install_or_doctor_failure_prevents_launch(self):
        for shell in SHELLS:
            for failure in ("FAKE_PIP_EXIT", "FAKE_DOCTOR_EXIT"):
                with self.subTest(shell=shell, failure=failure):
                    result, events = self.invoke(shell, "setup.sh", "--run", **{failure: "7"})
                    self.assertEqual(result.returncode, 7, result.stderr)
                    calls = self.app_calls(events)
                    self.assertEqual([call["args"][1:] for call in calls],
                                     [] if failure == "FAKE_PIP_EXIT" else [["doctor", "--no-gui", "--tui"]])

    def test_optimized_python_still_rejects_unsupported_interpreter_and_venv(self):
        for shell in SHELLS:
            for invalid in ("FAKE_BAD_PYTHON", "FAKE_BAD_VENV"):
                with self.subTest(shell=shell, invalid=invalid):
                    if invalid == "FAKE_BAD_VENV":
                        self.make_venv()
                    result, events = self.invoke(shell, "setup.sh", PYTHONOPTIMIZE="1", **{invalid: "1"})
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("incompatible" if invalid == "FAKE_BAD_VENV" else "Python 3.11 or 3.12", result.stderr)
                    self.assertEqual(self.app_calls(events), [])
                    self.assertFalse(any(event["args"][:2] == ["-m", "pip"] for event in events))
                    if invalid == "FAKE_BAD_VENV":
                        shutil.rmtree(self.project / ".venv")


if __name__ == "__main__":
    unittest.main()
