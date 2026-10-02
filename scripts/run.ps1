$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path $PSScriptRoot -Parent
$PythonPath = Join-Path $ProjectDir '.venv\Scripts\python.exe'
if (-not (Test-Path $PythonPath)) { throw 'Install the app with scripts\setup.ps1. See README.md.' }
& $PythonPath (Join-Path $ProjectDir 'whisper_m4a.py') @args
exit $LASTEXITCODE
