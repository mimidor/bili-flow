Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Utf8Encoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $Utf8Encoding
$OutputEncoding = $Utf8Encoding
try {
  chcp 65001 | Out-Null
} catch {
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$Root = $PSScriptRoot
$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"
$ScriptPath = Join-Path $Root "entrypoints\dev-stack.py"

if (-not (Test-Path $PythonExe)) {
  throw "Virtual environment interpreter not found: $PythonExe. Run uv sync first."
}

if (-not (Test-Path $ScriptPath)) {
  throw "Dev stack entrypoint not found: $ScriptPath"
}

& $PythonExe $ScriptPath
exit $LASTEXITCODE
