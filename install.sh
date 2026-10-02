#!/bin/sh
# Install a published release without Git. This file also works through stdin.
set -eu

case "${1:-}" in
  --help|-h)
    printf '%s\n' \
      'Usage: sh install.sh [--run] [--prefix DATA_DIR] [--bin-dir BIN_DIR]' \
      'Install whisper-local-ko from GitHub Releases. Add --run to open the TUI.' \
      'Default data: $HOME/.local/share/whisper-local-ko' \
      'Default launcher: $HOME/.local/bin/whisper-ko' \
      'Requires Python 3.11 or 3.12 and FFmpeg. Git is not required.'
    exit 0 ;;
esac

supports_python() {
  "$1" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 12) else 1)' >/dev/null 2>&1
}

python_bin=''
if [ -n "${WHISPER_PYTHON:-}" ]; then
  if supports_python "$WHISPER_PYTHON"; then
    python_bin=$WHISPER_PYTHON
  else
    printf '%s\n' 'WHISPER_PYTHON must select Python 3.11 or 3.12.' >&2
    exit 1
  fi
else
  if command -v brew >/dev/null 2>&1; then
    for python_version in 3.11 3.12; do
      brew_prefix=$(brew --prefix "python@$python_version" 2>/dev/null || true)
      candidate="$brew_prefix/bin/python$python_version"
      if [ -n "$brew_prefix" ] && supports_python "$candidate"; then
        python_bin=$candidate
        break
      fi
    done
  fi
  if [ -z "$python_bin" ]; then
    for candidate in python3.12 python3.11 python3; do
      if command -v "$candidate" >/dev/null 2>&1 && supports_python "$candidate"; then
        python_bin=$candidate
        break
      fi
    done
  fi
fi
if [ -z "$python_bin" ]; then
  printf '%s\n' 'Install Python 3.11 or 3.12. Set WHISPER_PYTHON to select its path.' >&2
  exit 1
fi

"$python_bin" - "$@" <<'WHISPER_INSTALL_PY'
"""Trusted bootstrap. Only execute release files after checksum validation."""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import os
from pathlib import Path, PurePosixPath
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request

VERSION = "0.1.2"
ARCHIVE = f"whisper_local_ko-{VERSION}.tar.gz"
ARCHIVE_ROOT = f"whisper_local_ko-{VERSION}"
RELEASE_URL = f"https://github.com/chaeyn/whisper-local-ko/releases/download/v{VERSION}"
MARKER = "# Managed by whisper-local-ko release installer v1"
MAX_DOWNLOAD = 32 * 1024 * 1024
MAX_EXTRACT = 128 * 1024 * 1024


class InstallError(Exception):
    pass


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise InstallError("The download redirected to an insecure URL.")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download(url, target, limit=MAX_DOWNLOAD):
    if urllib.parse.urlsplit(url).scheme != "https":
        raise InstallError("Release downloads require HTTPS.")
    opener = urllib.request.build_opener(HTTPSRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": f"whisper-local-ko/{VERSION}"})
    with opener.open(request, timeout=30) as source, target.open("xb") as output:
        if urllib.parse.urlsplit(source.geturl()).scheme != "https":
            raise InstallError("The download did not use HTTPS.")
        count = 0
        while block := source.read(64 * 1024):
            count += len(block)
            if count > limit:
                raise InstallError("The release download exceeds the size limit.")
            output.write(block)


def verify_archive(archive, checksums):
    matches = []
    for line in checksums.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == ARCHIVE:
            matches.append(fields[0])
    if (len(matches) != 1 or len(matches[0]) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in matches[0])):
        raise InstallError(f"SHA256SUMS.txt must contain one SHA-256 checksum for {ARCHIVE}.")
    with archive.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if not hmac.compare_digest(actual, matches[0].lower()):
        raise InstallError("The release checksum does not match. No release code was run.")


def extract_archive(archive, destination):
    """Validate every member before writing. Never materialize archive links."""
    with tarfile.open(archive, mode="r:gz") as source:
        members = source.getmembers()
        seen = set()
        total = 0
        for member in members:
            path = PurePosixPath(member.name)
            if (not member.name or "\\" in member.name or path.is_absolute()
                    or ".." in path.parts or not path.parts or path.parts[0] != ARCHIVE_ROOT
                    or not (member.isdir() or member.isfile()) or path in seen):
                raise InstallError(f"The archive contains an unsafe member: {member.name!r}")
            seen.add(path)
            total += member.size
            if member.size < 0 or total > MAX_EXTRACT or len(seen) > 10000:
                raise InstallError("The archive exceeds the extraction limit.")
        for member in members:
            path = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as input_file, path.open("xb") as output:
                    shutil.copyfileobj(input_file, output)
                # Do not propagate ownership, setuid bits, or write permissions.
                path.chmod(0o755 if member.mode & 0o111 else 0o644)
    project = destination / ARCHIVE_ROOT
    if not all((project / name).is_file() for name in ("scripts/setup.sh", "scripts/run.sh", "pyproject.toml")):
        raise InstallError("The release archive does not contain the required installation files.")
    return project


def launcher_state(path):
    """Only an ordinary file with our exact header is a managed launcher."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(metadata.st_mode):
        raise InstallError(f"The launcher path is occupied: {path}. Choose another --bin-dir.")
    with path.open("rb") as source:
        header = source.read(256)
    if not header.startswith(f"#!/bin/sh\n{MARKER}\n".encode()):
        raise InstallError(f"The launcher is not managed by this installer: {path}. Choose another --bin-dir.")
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


@contextmanager
def installation_lock(bin_dir):
    import fcntl
    path = bin_dir / ".whisper-local-ko-install.lock"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise InstallError(f"The installation lock is not an ordinary file: {path}")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise InstallError("Another installation is in progress. Wait for it to finish.") from error
        yield
    finally:
        os.close(descriptor)


def publish_launcher(launcher, project, expected_state):
    content = f'#!/bin/sh\n{MARKER}\nexec sh {shlex.quote(str(project / "scripts/run.sh"))} "$@"\n'
    descriptor, temporary_name = tempfile.mkstemp(prefix=".whisper-ko-", dir=launcher.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o755)
        if launcher_state(launcher) != expected_state:
            raise InstallError("The launcher changed during installation. The existing launcher was kept.")
        if expected_state is None:
            # Unlike replace(), link() cannot overwrite a newly created file.
            os.link(temporary, launcher)
        else:
            os.replace(temporary, launcher)
    finally:
        temporary.unlink(missing_ok=True)


def install(prefix, bin_dir):
    prefix = prefix.expanduser().resolve()
    bin_dir = bin_dir.expanduser().resolve()
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / "whisper-ko"
    with installation_lock(bin_dir):
        previous = launcher_state(launcher)
        releases = prefix / "releases"
        releases.mkdir(parents=True, exist_ok=True)
        # Keep this path for the life of the venv. Moving a venv breaks its scripts.
        release = Path(tempfile.mkdtemp(prefix=f"{VERSION}-", dir=releases))
        published = False
        try:
            print(f"Download whisper-local-ko {VERSION}.", flush=True)
            archive = release / ARCHIVE
            sums = release / "SHA256SUMS.txt"
            download(f"{RELEASE_URL}/SHA256SUMS.txt", sums, limit=1024 * 1024)
            download(f"{RELEASE_URL}/{ARCHIVE}", archive)
            verify_archive(archive, sums)
            print("Checksum verified. Install the release.", flush=True)
            project = extract_archive(archive, release)
            environment = dict(os.environ, WHISPER_PYTHON=sys.executable)
            subprocess.run(["sh", str(project / "scripts/setup.sh")], check=True, env=environment)
            publish_launcher(launcher, project, previous)
            published = True
        finally:
            if not published:
                shutil.rmtree(release)
        print(f"Installation complete. Run: {shlex.quote(str(launcher))}", flush=True)
        print("Previous successful releases remain in the data directory.", flush=True)
        return launcher


def launch(launcher):
    try:
        terminal = os.open("/dev/tty", os.O_RDONLY)
    except OSError as error:
        raise InstallError(f"Installation is complete. Open a terminal and run: {shlex.quote(str(launcher))}") from error
    os.dup2(terminal, 0)
    if terminal != 0:
        os.close(terminal)
    os.execv(str(launcher), [str(launcher)])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install a GitHub release without Git.")
    parser.add_argument("--run", action="store_true", help="Open the TUI after installation.")
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local/share/whisper-local-ko",
                        metavar="DATA_DIR", help="Directory for installed releases.")
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local/bin",
                        metavar="BIN_DIR", help="Directory for the whisper-ko launcher.")
    args = parser.parse_args(argv)
    system, machine = platform.system(), platform.machine().lower()
    if not ((system == "Darwin" and machine == "arm64")
            or (system == "Linux" and machine in ("x86_64", "amd64"))):
        raise InstallError("This shell installer supports macOS Apple Silicon and Linux x64.")
    if shutil.which("ffmpeg") is None:
        raise InstallError("Install FFmpeg and add it to PATH before you run this installer.")
    launcher = install(args.prefix, args.bin_dir)
    if args.run:
        launch(launcher)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstallError, OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("Installation interrupted.", file=sys.stderr)
        raise SystemExit(130)
WHISPER_INSTALL_PY
