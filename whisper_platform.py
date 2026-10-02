"""Model cache locks and FFmpeg microphone inputs for supported systems."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import os
from pathlib import Path
import platform
import re
import subprocess

from filelock import FileLock


@contextmanager
def model_download_lock(model_size: str):
    """Lock one model download and yield its cache folder on each supported OS."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", model_size):
        raise ValueError("Invalid model name.")
    cache = Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "whisper"
    cache.mkdir(parents=True, exist_ok=True)
    with FileLock(cache / f".{model_size}.download.lock"):
        yield cache


def audio_backend(system: str | None = None) -> str:
    system = system or platform.system()
    backends = {"Darwin": "avfoundation", "Linux": "pulse", "Windows": "dshow"}
    if system not in backends:
        raise RuntimeError(f"Microphone input is not supported on {system}. Use an audio file.")
    return backends[system]


def _avfoundation_devices(text: str) -> list[tuple[str, str]]:
    section = text.split("AVFoundation audio devices:", 1)
    if len(section) != 2:
        return []
    return re.findall(r"\[(\d+)\] (.+)", section[1])


def _dshow_devices(text: str) -> list[tuple[str, str]]:
    # FFmpeg lists a friendly name and then a unique alternative name.
    # Old builds use section headings; newer builds use media type suffixes.
    devices = []
    audio_section = False
    last_audio = None
    for line in text.splitlines():
        if "DirectShow audio devices" in line:
            audio_section = True
            last_audio = None
            continue
        if "DirectShow video devices" in line:
            audio_section = False
            last_audio = None
            continue
        alternative = re.search(r'Alternative name "(.*)"\s*$', line)
        if alternative:
            if last_audio is not None:
                devices[last_audio][1] = alternative.group(1)
            continue
        device = re.search(r'"(.*)"(?:\s+\(([^)]*)\))?\s*$', line)
        if not device:
            continue
        name, media = device.groups()
        if (media is not None and "audio" in media.split(", ")) or (media is None and audio_section):
            devices.append([name, None])
            last_audio = len(devices) - 1
        else:
            last_audio = None
    counts = Counter(name for name, _ in devices)
    # A colon separates DirectShow inputs. Use the alternative ID for such
    # names and for duplicate friendly names.
    return [(alternate if alternate and (":" in name or counts[name] > 1) else name, name)
            for name, alternate in devices]


def _pulse_devices(text: str) -> list[tuple[str, str]]:
    # `ffmpeg -sources pulse` prints: * source_name [description] (audio).
    return re.findall(r"^[ *]\s+(\S+)\s+\[(.*)\](?:\s+\([^\n]*\))?\s*$", text, re.MULTILINE)


def audio_devices(system: str | None = None) -> list[tuple[str, str]]:
    """Return FFmpeg input identifiers and display names. Do not open an input."""
    backend = audio_backend(system)
    command = ["ffmpeg", "-nostdin", "-hide_banner"]
    if backend == "pulse":
        command += ["-sources", "pulse"]
    else:
        command += ["-f", backend, "-list_devices", "true", "-i", "" if backend == "avfoundation" else "dummy"]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=15)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and add it to PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Microphone lookup timed out. Check the audio service and device connection.") from exc
    text = result.stdout + "\n" + result.stderr
    parsers = {"avfoundation": _avfoundation_devices, "dshow": _dshow_devices, "pulse": _pulse_devices}
    devices = parsers[backend](text)
    if not devices:
        hints = {
            "avfoundation": "Check microphone access in System Settings.",
            "dshow": "Check microphone access in Windows Settings.",
            "pulse": "Start PulseAudio or the PipeWire PulseAudio service.",
        }
        detail = text.strip()[-800:]
        raise RuntimeError(f"No audio inputs found. FFmpeg must support {backend}. {hints[backend]}"
                           + (f"\n{detail}" if detail else ""))
    return devices


def audio_input_arguments(device: str = "default", system: str | None = None) -> list[str]:
    """Build FFmpeg input arguments without shell quoting or video capture."""
    backend = audio_backend(system)
    if not device or "\x00" in device:
        raise ValueError("Select a valid audio input.")
    if backend == "avfoundation":
        return ["-f", backend, "-i", f"none:{device}"]
    if backend == "pulse":
        return ["-f", backend, "-i", device]
    if device == "default":
        device = audio_devices(system)[0][0]
    if ":" in device:
        matches = [identifier for identifier, name in audio_devices(system) if name == device and ":" not in identifier]
        if not matches:
            raise ValueError("This input name contains a colon. Select its alternative name from --list-devices.")
        device = matches[0]
    return ["-f", backend, "-i", f"audio={device}"]
