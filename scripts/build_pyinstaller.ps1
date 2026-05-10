$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$ReleaseDir = Join-Path $Root 'dist\release'
$BuildDir = Join-Path $Root 'build\pyinstaller'
$ToolsDir = Join-Path $ReleaseDir 'tools'
$WebDistIndex = Join-Path $Root 'web\dist\index.html'

function Invoke-Uv {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Args
  )
  & uv @Args
  if ($LASTEXITCODE -ne 0) {
    throw "uv command failed: uv $($Args -join ' ')"
  }
}

function Copy-YtDlpBinary {
  param(
    [Parameter(Mandatory = $true)]
    [string]$DestinationPath
  )

  $ytDlpPath = (& uv run python -c "import shutil; print(shutil.which('yt-dlp') or '')").Trim()
  if ($ytDlpPath -and (Test-Path $ytDlpPath) -and ([IO.Path]::GetExtension($ytDlpPath).ToLowerInvariant() -eq '.exe')) {
    Copy-Item -Path $ytDlpPath -Destination $DestinationPath -Force
  } else {
    $downloadUrl = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe'
    Write-Host "Downloading yt-dlp.exe from $downloadUrl" -ForegroundColor Yellow
    Invoke-WebRequest -Uri $downloadUrl -OutFile $DestinationPath
  }

  if (-not (Test-Path $DestinationPath)) {
    throw "Failed to prepare yt-dlp.exe at $DestinationPath"
  }

  & $DestinationPath --version | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Prepared yt-dlp.exe is not runnable: $DestinationPath"
  }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv was not found. Please install uv first."
}

Push-Location $Root
try {
  if (Test-Path $ReleaseDir) {
    Remove-Item $ReleaseDir -Recurse -Force
  }
  New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null
  New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null

  Invoke-Uv -Args @('sync', '--extra', 'build')

  if (-not (Test-Path $WebDistIndex)) {
    throw "Missing web/dist/index.html. Run scripts\\build_frontend.ps1 before building the installer."
  }

  $packagingSpecs = @(
    @{ Name = 'bili-backend'; Spec = 'packaging/backend.spec' },
    @{ Name = 'bili-scheduler'; Spec = 'packaging/scheduler.spec' },
    @{ Name = 'bili-launcher'; Spec = 'packaging/launcher.spec' }
  )

  foreach ($item in $packagingSpecs) {
    $workpath = Join-Path $BuildDir $item.Name
    New-Item -ItemType Directory -Path $workpath -Force | Out-Null
    Invoke-Uv -Args @(
      'run', 'pyinstaller',
      '--noconfirm',
      '--clean',
      '--distpath', $ReleaseDir,
      '--workpath', $workpath,
      $item.Spec
      )
  }

  Copy-YtDlpBinary -DestinationPath (Join-Path $ToolsDir 'yt-dlp.exe')

  $ffmpegDir = (& uv run python -c "from app.utils.external_tools import resolve_ffmpeg_bin; p = resolve_ffmpeg_bin(); print(str(p) if p else '')").Trim()
  if ($ffmpegDir) {
    $ffmpegExe = Join-Path $ffmpegDir 'ffmpeg.exe'
    $ffprobeExe = Join-Path $ffmpegDir 'ffprobe.exe'
    if (Test-Path $ffmpegExe) {
      Copy-Item -Path $ffmpegExe -Destination (Join-Path $ToolsDir 'ffmpeg.exe') -Force
    }
    if (Test-Path $ffprobeExe) {
      Copy-Item -Path $ffprobeExe -Destination (Join-Path $ToolsDir 'ffprobe.exe') -Force
    }
  } else {
    Write-Warning "ffmpeg was not found. Install ffmpeg or set FFMPEG_LOCATION before building."
  }

  Copy-Item -Path (Join-Path $Root '.env.example') -Destination (Join-Path $ReleaseDir '.env.example') -Force

  Write-Host "PyInstaller build completed: $ReleaseDir" -ForegroundColor Green
} finally {
  Pop-Location
}
