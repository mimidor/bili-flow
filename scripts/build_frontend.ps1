$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$WebDir = Join-Path $Root 'web'

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm was not found. Please install Node.js 22+ and reopen PowerShell."
}

if (-not (Test-Path $WebDir)) {
  throw "web directory not found: $WebDir"
}

Push-Location $Root
try {
  Push-Location $WebDir
  try {
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm install failed" }

    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
  } finally {
    Pop-Location
  }
} finally {
  Pop-Location
}
