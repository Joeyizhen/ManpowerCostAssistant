# Project-local tests; use an absolute, unique scratch directory in this workspace.
$ErrorActionPreference = 'Stop'
$taskProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskProjectRoot
$taskScratch = Join-Path $taskProjectRoot ('local_data/test-run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $taskProjectRoot 'local_data') -Force | Out-Null
& "$taskProjectRoot/.venv/Scripts/python.exe" -m pytest -q "--basetemp=$taskScratch"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$taskProjectRoot/.venv/Scripts/python.exe" -m ruff check app.py hybrid_inputs.py journey_inputs.py services scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$taskProjectRoot/.venv/Scripts/python.exe" -m scripts.evaluate_live --split development --limit 3
exit $LASTEXITCODE
