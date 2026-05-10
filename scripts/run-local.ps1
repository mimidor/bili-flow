param(
  [ValidateSet("start", "stop", "restart", "status", "build")]
  [string]$Action = "start",

  [switch]$RebuildFrontend
)

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
$RuntimeDir = Join-Path $Root ".runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$StateFile = Join-Path $RuntimeDir "local-stack.json"
$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"
$EntrypointDir = Join-Path $Root "entrypoints"
$WebDistDir = Join-Path $Root "web\dist"
$BuildScript = Join-Path $Root "scripts\build_frontend.ps1"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

function Ensure-Directory {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
  }
}

function Read-State {
  if (-not (Test-Path $StateFile)) {
    return @()
  }

  try {
    $content = Get-Content -Path $StateFile -Raw -Encoding UTF8
    if (-not $content.Trim()) {
      return @()
    }
    return @($content | ConvertFrom-Json)
  } catch {
    return @()
  }
}

function Save-State {
  param([object[]]$Entries)
  Ensure-Directory -Path $RuntimeDir
  $Entries | ConvertTo-Json -Depth 6 | Set-Content -Path $StateFile -Encoding UTF8
}

function Test-ProcessAlive {
  param([int]$Pid)
  return [bool](Get-Process -Id $Pid -ErrorAction SilentlyContinue)
}

function New-LogPath {
  param(
    [string]$Name,
    [string]$Kind
  )
  Ensure-Directory -Path $LogDir
  return Join-Path $LogDir ($Name + "-" + $Timestamp + "." + $Kind + ".log")
}

function Start-ManagedProcess {
  param(
    [string]$Name,
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory
  )

  $stdout = New-LogPath -Name $Name -Kind "out"
  $stderr = New-LogPath -Name $Name -Kind "err"
  New-Item -ItemType File -Path $stdout -Force | Out-Null
  New-Item -ItemType File -Path $stderr -Force | Out-Null

  $process = Start-Process `
    -FilePath $FilePath `
    -ArgumentList $Arguments `
    -WorkingDirectory $WorkingDirectory `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

  return [pscustomobject]@{
    name = $Name
    pid = $process.Id
    started_at = (Get-Date).ToString("s")
    command = "$FilePath $($Arguments -join ' ')"
    stdout = $stdout
    stderr = $stderr
  }
}

function Stop-ManagedProcess {
  param([pscustomobject]$Entry)

  if ($null -eq $Entry.pid) {
    return
  }

  if (Test-ProcessAlive -Pid ([int]$Entry.pid)) {
    & taskkill /PID ([int]$Entry.pid) /T /F | Out-Null
  }
}

function Ensure-FrontendBuilt {
  if (-not (Test-Path $BuildScript)) {
    throw "Frontend build script not found: $BuildScript"
  }

  if ($RebuildFrontend -or -not (Test-Path $WebDistDir)) {
    Write-Host "Building frontend dist..."
    & powershell -ExecutionPolicy Bypass -File $BuildScript
    if ($LASTEXITCODE -ne 0) {
      throw "Frontend build failed."
    }
  }
}

function Show-Status {
  $entries = Read-State
  if (-not $entries -or $entries.Count -eq 0) {
    Write-Host "No local stack records found."
    return
  }

  foreach ($entry in $entries) {
    $alive = Test-ProcessAlive -Pid ([int]$entry.pid)
    $state = if ($alive) { "running" } else { "stopped" }
    Write-Host ("{0} | PID={1} | {2}" -f $entry.name, $entry.pid, $state)
  }
}

function Start-Stack {
  if (-not (Test-Path $PythonExe)) {
    throw "Virtual environment interpreter not found: $PythonExe. Run uv sync first."
  }

  $existing = @(Read-State | Where-Object { $_ -and (Test-ProcessAlive -Pid ([int]$_.pid)) })
  if ($existing.Count -gt 0) {
    Write-Host "Local stack is already running. Run stop or restart first."
    foreach ($entry in $existing) {
      Write-Host ("{0} | PID={1}" -f $entry.name, $entry.pid)
    }
    return
  }

  Ensure-FrontendBuilt

  $backend = Start-ManagedProcess `
    -Name "backend" `
    -FilePath $PythonExe `
    -Arguments @((Join-Path $EntrypointDir "entrypoint-backend.py")) `
    -WorkingDirectory $Root

  Start-Sleep -Seconds 1

  $scheduler = Start-ManagedProcess `
    -Name "scheduler" `
    -FilePath $PythonExe `
    -Arguments @((Join-Path $EntrypointDir "entrypoint-scheduler.py")) `
    -WorkingDirectory $Root

  Save-State -Entries @($backend, $scheduler)

  Write-Host "Local stack started:"
  Write-Host ("- Admin UI/API: http://127.0.0.1:8000")
  Write-Host ("- Scheduler: entrypoints\\entrypoint-scheduler.py")
  Write-Host ("- Frontend is served from web/dist by backend")
  Write-Host ("Logs: {0}" -f $LogDir)
}

function Stop-Stack {
  $entries = Read-State
  if (-not $entries -or $entries.Count -eq 0) {
    Write-Host "No local stack records found to stop."
    return
  }

  foreach ($entry in $entries) {
    Stop-ManagedProcess -Entry $entry
  }

  if (Test-Path $StateFile) {
    Remove-Item $StateFile -Force
  }

  Write-Host "Stopped backend and scheduler."
}

switch ($Action) {
  "start" { Start-Stack }
  "stop" { Stop-Stack }
  "restart" { Stop-Stack; Start-Stack }
  "status" { Show-Status }
  "build" { Ensure-FrontendBuilt }
}
