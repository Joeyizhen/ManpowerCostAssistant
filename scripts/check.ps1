# Project-local tests; use an absolute, unique scratch directory in this workspace.
$ErrorActionPreference = 'Stop'
$taskProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskProjectRoot
$taskScratch = Join-Path $taskProjectRoot ('local_data/q' + [guid]::NewGuid().ToString('N').Substring(0, 6))
New-Item -ItemType Directory -Path (Join-Path $taskProjectRoot 'local_data') -Force | Out-Null
$taskTemporary = Join-Path $taskProjectRoot 'local_data/qa-tmp'
New-Item -ItemType Directory -Path $taskTemporary -Force | Out-Null
$env:TEMP = $taskTemporary
$env:TMP = $taskTemporary
& "$taskProjectRoot/.venv/Scripts/python.exe" -m pytest -q "--basetemp=$taskScratch"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$taskProjectRoot/.venv/Scripts/python.exe" -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$taskProjectRoot/.venv/Scripts/python.exe" -m scripts.evaluate_live --split development --limit 3
exit $LASTEXITCODE
