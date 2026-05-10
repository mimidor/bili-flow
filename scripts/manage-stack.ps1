param(
  [ValidateSet("start", "stop", "restart", "status")]
  [string]$Action = "start"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Utf8Encoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $Utf8Encoding
$OutputEncoding = $Utf8Encoding
try {
  chcp 65001 | Out-Null
} catch {
  # Ignore shells that already use UTF-8 or do not support chcp.
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeDir = Join-Path $Root ".runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$PidFile = Join-Path $RuntimeDir "stack-processes.json"
$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"
$WebDir = Join-Path $Root "web"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

function Ensure-Directory {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
  }
}

function Resolve-NpmCommand {
  $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if ($npm) {
    return $npm.Source
  }
  $npm = Get-Command npm -ErrorAction SilentlyContinue
  if ($npm) {
    return $npm.Source
  }
  throw "npm not found. Install Node.js and make sure npm is on PATH."
}

function Read-State {
  if (-not (Test-Path $PidFile)) {
    return @()
  }

  try {
    $content = Get-Content -Path $PidFile -Raw -Encoding UTF8
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
  $Entries | ConvertTo-Json -Depth 6 | Set-Content -Path $PidFile -Encoding UTF8
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

function Show-Status {
  $entries = Read-State
  if (-not $entries -or $entries.Count -eq 0) {
    Write-Host "No running service records found."
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

  $npm = Resolve-NpmCommand

  $existing = @(Read-State | Where-Object { $_ -and (Test-ProcessAlive -Pid ([int]$_.pid)) })
  if ($existing.Count -gt 0) {
    Write-Host "Services are already running. Run stop or restart first."
    foreach ($entry in $existing) {
      Write-Host ("{0} | PID={1}" -f $entry.name, $entry.pid)
    }
    return
  }

  Ensure-Directory -Path $RuntimeDir

  $backend = Start-ManagedProcess `
    -Name "backend" `
    -FilePath $PythonExe `
    -Arguments @("-m", "uvicorn", "admin_backend.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $Root

  $frontend = Start-ManagedProcess `
    -Name "frontend" `
    -FilePath $npm `
    -Arguments @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
    -WorkingDirectory $WebDir

  $scheduler = Start-ManagedProcess `
    -Name "scheduler" `
    -FilePath $PythonExe `
    -Arguments @("main.py") `
    -WorkingDirectory $Root

  Save-State -Entries @($backend, $frontend, $scheduler)

  Write-Host "Services started:"
  Write-Host ("- Backend: http://127.0.0.1:8000/docs")
  Write-Host ("- Frontend: http://127.0.0.1:5173")
  Write-Host ("- Scheduler: main.py")
  Write-Host ("Logs: {0}" -f $LogDir)
}

function Stop-Stack {
  $entries = Read-State
  if (-not $entries -or $entries.Count -eq 0) {
    Write-Host "No services were found to stop."
    return
  }

  foreach ($entry in $entries) {
    Stop-ManagedProcess -Entry $entry
  }

  if (Test-Path $PidFile) {
    Remove-Item $PidFile -Force
  }

  Write-Host "Stopped frontend, backend, and scheduler."
}

switch ($Action) {
  "start" { Start-Stack }
  "stop" { Stop-Stack }
  "restart" { Stop-Stack; Start-Stack }
  "status" { Show-Status }
}
