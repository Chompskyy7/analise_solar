param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectRoot,
  [int]$StartupTimeoutSec = 45
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Resolve-ProjectPath {
  param([string]$RawPath)
  $clean = $RawPath.Trim('"').Trim().TrimEnd("\")
  (Resolve-Path -LiteralPath $clean).Path.TrimEnd("\")
}

function Find-ActiveSidecar {
  param([string]$ExeDir)
  $candidates = @(
    "pipeline-solar-backend-x86_64-pc-windows-msvc.exe",
    "pipeline-solar-backend.exe"
  )
  foreach ($name in $candidates) {
    $candidate = Join-Path $ExeDir $name
    if (Test-Path -LiteralPath $candidate) {
      return $candidate
    }
  }
  throw "Sidecar ativo nao encontrado em $ExeDir"
}

function Stop-SmokeProcesses {
  $images = @(
    "analise-solar-plus.exe",
    "pipeline-solar-backend.exe",
    "pipeline-solar-backend-x86_64-pc-windows-msvc.exe"
  )
  foreach ($image in $images) {
    cmd /c "taskkill /F /IM $image >nul 2>nul" | Out-Null
  }
}

$root = Resolve-ProjectPath -RawPath $ProjectRoot
$appExe = Join-Path $root "src-tauri\target\release\analise-solar-plus.exe"
if (-not (Test-Path -LiteralPath $appExe)) {
  throw "Executavel nao encontrado: $appExe"
}

$exeDir = Split-Path -Parent $appExe
$packagedSidecar = Join-Path $root "src-tauri\binaries\pipeline-solar-backend-x86_64-pc-windows-msvc.exe"
if (-not (Test-Path -LiteralPath (Join-Path $exeDir "pipeline-solar-backend.exe")) -and (Test-Path -LiteralPath $packagedSidecar)) {
  Copy-Item -LiteralPath $packagedSidecar -Destination (Join-Path $exeDir "pipeline-solar-backend.exe") -Force
}
$activeSidecar = Find-ActiveSidecar -ExeDir $exeDir

$runtimeDir = Join-Path $env:LOCALAPPDATA "br.pipeline.solar.modernizacao\runtime-update"
$stateFile = Join-Path $runtimeDir "update-runtime-state.json"
$noticeFile = Join-Path $runtimeDir "rollback-notice.json"
$backupFile = Join-Path $runtimeDir "known-good-sidecar.exe"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
Copy-Item -LiteralPath $activeSidecar -Destination $backupFile -Force

$statePayload = @{
  last_started_version = "0.2.9"
  pending_update = $null
  rollback_notice = $null
} | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText(
  $stateFile,
  $statePayload,
  (New-Object System.Text.UTF8Encoding($false))
)
if (Test-Path -LiteralPath $noticeFile) {
  Remove-Item -LiteralPath $noticeFile -Force
}

Stop-SmokeProcesses

$originalEnv = $env:PIPELINE_SOLAR_FORCE_HEALTHCHECK_FAIL
$env:PIPELINE_SOLAR_FORCE_HEALTHCHECK_FAIL = "1"
$appProc = $null

try {
  $appProc = Start-Process -FilePath $appExe -PassThru

  $deadline = (Get-Date).AddSeconds($StartupTimeoutSec)
  $notice = $null
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 600
    if (Test-Path -LiteralPath $noticeFile) {
      $notice = Get-Content -LiteralPath $noticeFile -Raw | ConvertFrom-Json
      break
    }
  }

  if ($null -eq $notice) {
    throw "Arquivo de rollback nao foi gerado no prazo: $noticeFile"
  }

  if (-not $notice.restored_from_backup) {
    throw "Rollback detectado sem restauracao do backup."
  }

  Write-Host "[OK] Rollback automatico disparado."
  Write-Host ("[OK] De: " + [string]$notice.from_version + " -> " + [string]$notice.to_version)
  Write-Host ("[OK] Canal: " + [string]$notice.channel)
  Write-Host ("[OK] Motivo: " + [string]$notice.reason)
  Write-Host ("[OK] Notice: " + $noticeFile)
} finally {
  if ($null -eq $originalEnv) {
    Remove-Item Env:PIPELINE_SOLAR_FORCE_HEALTHCHECK_FAIL -ErrorAction SilentlyContinue
  } else {
    $env:PIPELINE_SOLAR_FORCE_HEALTHCHECK_FAIL = $originalEnv
  }

  if ($appProc) {
    $running = Get-Process -Id $appProc.Id -ErrorAction SilentlyContinue
    if ($running) {
      [void]$running.CloseMainWindow()
      Start-Sleep -Milliseconds 1200
      if (-not $running.HasExited) {
        Stop-Process -Id $running.Id -Force -ErrorAction SilentlyContinue
      }
    }
  }

  Stop-SmokeProcesses
}
