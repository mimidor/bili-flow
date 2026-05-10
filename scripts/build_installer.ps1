$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$ReleaseDir = Join-Path $Root 'dist\release'
$InstallerOutDir = Join-Path $Root 'dist\installer'
$InstallerScript = Join-Path $Root 'packaging\installer.iss'

function Get-ProjectVersion {
  $version = & uv run python -c "import pathlib, tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to read project version from pyproject.toml"
  }
  return $version.Trim()
}

if (-not (Test-Path $ReleaseDir)) {
  throw "Release directory not found: $ReleaseDir. Run build_pyinstaller.ps1 first."
}

if (-not (Test-Path $InstallerScript)) {
  throw "Installer script not found: $InstallerScript"
}

$iscc = $env:ISCC_EXE
if (-not $iscc) {
  $isccCmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($isccCmd) {
    $iscc = $isccCmd.Source
  }
}
if (-not $iscc) {
  throw "ISCC.exe was not found. Install Inno Setup 6 and set ISCC_EXE if needed."
}

New-Item -ItemType Directory -Path $InstallerOutDir -Force | Out-Null

Push-Location $Root
try {
  $version = Get-ProjectVersion
  & $iscc "/DSourceDir=$ReleaseDir" "/DAppVersion=$version" "/O$InstallerOutDir" $InstallerScript
  if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed"
  }

  Write-Host "Installer build completed in $InstallerOutDir" -ForegroundColor Green
} finally {
  Pop-Location
}
