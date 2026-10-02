"""Prepare the versioned GitHub release assets after building distributions."""

import hashlib
from pathlib import Path
import re
import shutil
import tomllib


def prepare_release(root: Path) -> list[Path]:
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    installer = root / "install.sh"
    match = re.search(r'^VERSION = "([^"]+)"$', installer.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None or match.group(1) != version:
        raise ValueError("The install.sh version must match pyproject.toml before release.")
    dist = root / "dist"
    assets = [dist / f"whisper_local_ko-{version}-py3-none-any.whl",
              dist / f"whisper_local_ko-{version}.tar.gz"]
    for asset in assets:
        if not asset.is_file():
            raise FileNotFoundError(f"Build the distribution before release: {asset.name}")
    shutil.copyfile(installer, dist / "install.sh")
    assets.append(dist / "install.sh")
    lines = []
    for asset in assets:
        with asset.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        lines.append(f"{digest}  {asset.name}\n")
    manifest = dist / "SHA256SUMS.txt"
    manifest.write_text("".join(lines), encoding="utf-8", newline="\n")
    return [*assets, manifest]


if __name__ == "__main__":
    for path in prepare_release(Path(__file__).resolve().parents[1]):
        print(f"Ready: {path.name}")
