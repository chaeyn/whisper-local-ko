param([string]$PythonVersion = '3.11')
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if ($PythonVersion -notin @('3.11', '3.12')) { throw 'Use Python 3.11 or 3.12.' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw 'Install FFmpeg and add it to PATH. See README.md. Then open a new terminal.'
}
if (Test-Path '.venv') {
    if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Rename the incompatible .venv, then try again.' }
    & .venv\Scripts\python.exe -c 'import sys; assert (3, 11) <= sys.version_info[:2] <= (3, 12)'
    if ($LASTEXITCODE -ne 0) { throw 'Rename the incompatible .venv, then try again.' }
} else {
    & py "-$PythonVersion" -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install the selected Python version and its py launcher.' }
}
& .venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip update failed.' }
& .venv\Scripts\python.exe -m pip install 'torch==2.8.0' --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
& .venv\Scripts\python.exe -m pip install .
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
& "$PSScriptRoot\run.ps1" doctor --no-gui --tui
exit $LASTEXITCODE
