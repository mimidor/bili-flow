$ErrorActionPreference = 'Stop'

$Utf8Encoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $Utf8Encoding
$OutputEncoding = $Utf8Encoding
try {
  chcp 65001 | Out-Null
} catch {
  # Ignore shells that do not expose chcp or already run in UTF-8 mode.
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Invoke-NpmInstall {
  param(
    [Parameter(Mandatory = $true)]
    [string]$WorkingDirectory,
    [string[]]$ExtraArgs = @()
  )

  if (-not (Test-Path $WorkingDirectory)) {
    throw "Directory not found: $WorkingDirectory"
  }

  Write-Host "Installing npm dependencies in $WorkingDirectory ..." -ForegroundColor Cyan
  Push-Location $WorkingDirectory
  try {
    $args = @('install', '--no-audit', '--no-fund') + $ExtraArgs
    & npm @args
    if ($LASTEXITCODE -ne 0) {
      throw "npm install failed in $WorkingDirectory"
    }
  } finally {
    Pop-Location
  }
}

Write-Host "Checking Node.js / npm ..." -ForegroundColor Cyan
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm was not found. Please install Node.js 22+ and reopen PowerShell."
}

Invoke-NpmInstall -WorkingDirectory (Join-Path $PSScriptRoot 'web')

Write-Host ""
Write-Host "Installation completed." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Start backend:        python entrypoints\\entrypoint-backend.py" -ForegroundColor Yellow
Write-Host "  2. Start scheduler:      python entrypoints\\entrypoint-scheduler.py" -ForegroundColor Yellow
Write-Host "  3. Start frontend:       cd web; npm run dev" -ForegroundColor Yellow
Write-Host ""
Write-Host "If you want backend + scheduler together, run: python entrypoints\\entrypoint.py" -ForegroundColor Yellow
