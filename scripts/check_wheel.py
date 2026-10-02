"""Install the built wheel, then test imports outside the checkout."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
wheels = list((root / 'dist').glob('whisper_local_ko-*.whl'))
if len(wheels) != 1:
    raise SystemExit('Expected one app wheel in dist/.')
wheel = wheels[0]
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    for module in ('whisper_m4a', 'whisper_tui', 'whisper_live', 'whisper_platform'):
        assert f'{module}.py' in names, f'Missing module: {module}'
    assert not any(name.startswith(('work/', 'tests/', '.venv/')) for name in names)
subprocess.run([sys.executable, '-m', 'pip', 'install', '--force-reinstall', '--no-deps', str(wheel)], check=True)
with tempfile.TemporaryDirectory() as directory:
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    subprocess.run([sys.executable, '-c',
                    'import whisper_m4a, whisper_tui, whisper_live, whisper_platform; '
                    'raise SystemExit(whisper_m4a.main(["--version"]))'],
                   cwd=directory, env=environment, check=True)
    subprocess.run([sys.executable, '-m', 'whisper_m4a', '--help'],
                   cwd=directory, env=environment, check=True, stdout=subprocess.DEVNULL)
print(f'Wheel imports and CLI passed: {wheel.name}')
