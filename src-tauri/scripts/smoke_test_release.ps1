param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectRoot,
  [string]$ClientName = "Cliente Smoke Test"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Stop-AppProcesses {
  $images = @(
    "analise-solar-plus.exe",
    "pipeline-solar-backend.exe",
    "pipeline-solar-backend-x86_64-pc-windows-msvc.exe"
  )
  foreach ($image in $images) {
    cmd /c "taskkill /F /IM $image >nul 2>nul" | Out-Null
  }
}

function Wait-Health {
  param([int]$Attempts = 24, [int]$DelayMs = 500)
  for ($i = 1; $i -le $Attempts; $i++) {
    Start-Sleep -Milliseconds $DelayMs
    try {
      return Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -Method Get -TimeoutSec 1
    } catch {
      continue
    }
  }
  throw "Health check nao respondeu dentro do prazo."
}

function Get-SmokeAppProcesses {
  Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -like "analise-solar-plus" -or $_.ProcessName -like "pipeline-solar-backend*"
  }
}

function Format-SmokeProcessDetails {
  param([Parameter(Mandatory = $true)]$Processes)

  $Processes | Sort-Object ProcessName, Id | ForEach-Object {
    "$($_.ProcessName):$($_.Id)"
  }
}

if (-not ("Win32WindowProbe" -as [type])) {
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win32WindowProbe {
  [DllImport("user32.dll")]
  public static extern bool IsHungAppWindow(IntPtr hWnd);
}
"@
}

$projectRootClean = $ProjectRoot.Trim('"').Trim()
$projectRootClean = $projectRootClean.TrimEnd("\")
$root = (Resolve-Path -LiteralPath $projectRootClean).Path.TrimEnd("\")
$sidecar = Join-Path $root "src-tauri\binaries\pipeline-solar-backend-x86_64-pc-windows-msvc.exe"
$appExe = Join-Path $root "src-tauri\target\release\analise-solar-plus.exe"
$smokeBase = Join-Path $root "_smoke_clientes"

if (-not (Test-Path -LiteralPath $sidecar)) {
  throw "Sidecar nao encontrado: $sidecar"
}

if (-not (Test-Path -LiteralPath $appExe)) {
  throw "Executavel desktop nao encontrado: $appExe"
}

Stop-AppProcesses

# Etapa 1: sidecar direto
$sidecarProc = Start-Process -FilePath $sidecar -WindowStyle Hidden -PassThru
$health = Wait-Health
if (-not $health.ok) {
  throw "Health retornou ok=false."
}

$originalSettings = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/settings" -Method Get -TimeoutSec 3
if (-not $originalSettings.baseDir -or -not $originalSettings.downloadsDir -or -not $originalSettings.outputDir) {
  throw "Settings nao retornou diretorios base esperados."
}
$originalSettingsJson = $originalSettings | ConvertTo-Json -Depth 12

$clientsStart = Get-Date
$clients = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/clients" -Method Get -TimeoutSec 4
$clientsElapsedMs = [int](([DateTime]::UtcNow - $clientsStart.ToUniversalTime()).TotalMilliseconds)
if ($null -eq $clients.clients) {
  throw "Endpoint /api/clients sem campo clients."
}
if ($clientsElapsedMs -gt 6000) {
  throw ("Endpoint /api/clients lento na inicializacao: " + $clientsElapsedMs + " ms")
}

$create = $null
try {
  $emptyDownloads = Join-Path $root "_smoke_empty_downloads"
  $smokeOutput = Join-Path $root "_smoke_output"
  New-Item -ItemType Directory -Force -Path $smokeBase | Out-Null
  New-Item -ItemType Directory -Force -Path $emptyDownloads | Out-Null
  New-Item -ItemType Directory -Force -Path $smokeOutput | Out-Null

  $setSmokeSettings = @{
    baseDir = $smokeBase
    downloadsDir = $emptyDownloads
    outputDir = $smokeOutput
    defaultDays = 3
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/settings" -Method Post -ContentType "application/json" -Body $setSmokeSettings -TimeoutSec 5 | Out-Null

  $payload = @{
    client  = $ClientName
    baseDir = $smokeBase
  } | ConvertTo-Json

  $create = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/clients/create" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 10
  if (-not $create.clientDir) {
    throw "Create-client nao retornou clientDir."
  }

  $previewPayload = @{
    client = $ClientName
    origin = $emptyDownloads
    days = 3
    importDownloads = $false
    quarantine = $true
  } | ConvertTo-Json
  $preview = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/downloads/preview" -Method Post -ContentType "application/json" -Body $previewPayload -TimeoutSec 10
  if ($null -eq $preview.counts) {
    throw "Preview de downloads nao retornou counts."
  }

  $preflightPayload = @{
    client = $ClientName
    downloads = $emptyDownloads
    outputDir = $smokeOutput
    days = 3
    importDownloads = $false
  } | ConvertTo-Json
  $preflight = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/preflight" -Method Post -ContentType "application/json" -Body $preflightPayload -TimeoutSec 15
  if ($null -eq $preflight.items) {
    throw "Preflight nao retornou itens."
  }

  $runPayload = @{
    client = $ClientName
    downloads = $emptyDownloads
    outputDir = $smokeOutput
    days = 3
    importDownloads = $false
    quarantine = $true
  } | ConvertTo-Json
  $runResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/pipeline/run" -Method Post -ContentType "application/json" -Body $runPayload -TimeoutSec 15
  $jobId = [string]($runResponse.id)
  if (-not $jobId) {
    throw "Execucao nao retornou job id."
  }

  $finalJob = $null
  for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 750
    $job = Invoke-RestMethod -Uri ("http://127.0.0.1:8765/api/jobs/" + [Uri]::EscapeDataString($jobId)) -Method Get -TimeoutSec 3
    $status = [string]$job.status
    if ($status -and $status -notin @("queued", "running")) {
      $finalJob = $job
      break
    }
  }
  if ($null -eq $finalJob) {
    throw "Tarefa de smoke nao finalizou no prazo."
  }
  if ([string]$finalJob.status -notin @("done", "error", "cancelled")) {
    throw ("Status final inesperado da tarefa de smoke: " + [string]$finalJob.status)
  }

  $diagnostics = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/diagnostics/run" -Method Post -ContentType "application/json" -Body "{}" -TimeoutSec 20
  if ($null -eq $diagnostics.items) {
    throw "Diagnostico nao retornou itens."
  }
} finally {
  if ($originalSettingsJson) {
    try {
      Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/settings" -Method Post -ContentType "application/json" -Body $originalSettingsJson -TimeoutSec 5 | Out-Null
    } catch {
      Write-Warning "Nao foi possivel restaurar configuracoes apos smoke."
    }
  }
  if ($sidecarProc) {
    Stop-Process -Id $sidecarProc.Id -Force -ErrorAction SilentlyContinue
  }
  Stop-AppProcesses
}

# Etapa 2: app desktop + close
$appProc = Start-Process -FilePath $appExe -PassThru
try { [void]$appProc.WaitForInputIdle(10000) } catch {}

$mainHandle = [IntPtr]::Zero
for ($i = 0; $i -lt 15; $i++) {
  Start-Sleep -Milliseconds 500
  $appProc.Refresh()
  if ($appProc.MainWindowHandle -ne 0) {
    $mainHandle = [IntPtr]$appProc.MainWindowHandle
    break
  }
}
if ($mainHandle -eq [IntPtr]::Zero) {
  throw "Janela principal nao ficou disponivel no prazo."
}

if ([Win32WindowProbe]::IsHungAppWindow($mainHandle)) {
  throw "App abriu, mas a janela principal ficou sem resposta."
}

$runningAfterStart = Get-Process | Where-Object {
  $_.ProcessName -like "analise-solar-plus" -or $_.ProcessName -like "pipeline-solar-backend*"
}
if (-not $runningAfterStart) {
  throw "App abriu sem processos esperados."
}

$gui = Get-Process -Id $appProc.Id -ErrorAction SilentlyContinue
if ($gui) {
  [void]$gui.CloseMainWindow()
}

$closeWaitsMs = @(500, 1000, 1500, 2000, 3000, 5000)
$runningAfterClose = Get-SmokeAppProcesses
foreach ($delayMs in $closeWaitsMs) {
  if (-not $runningAfterClose) {
    break
  }
  Start-Sleep -Milliseconds $delayMs
  $runningAfterClose = Get-SmokeAppProcesses
}

if ($runningAfterClose) {
  $backendRemaining = $runningAfterClose | Where-Object { $_.ProcessName -like "pipeline-solar-backend*" }
  if ($backendRemaining) {
    try {
      Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/shutdown" -Method Post -TimeoutSec 5 | Out-Null
    } catch {
      Write-Warning "Nao foi possivel acionar /api/shutdown durante o smoke."
    }
    Start-Sleep -Milliseconds 1500
    $runningAfterClose = Get-SmokeAppProcesses
  }
}

if ($runningAfterClose) {
  $details = Format-SmokeProcessDetails -Processes $runningAfterClose
  throw ("Processos remanescentes apos fechar app: " + ($details -join ", "))
}

Write-Host "[OK] Smoke test release passou."
Write-Host ("[OK] Versao backend: " + $health.version)
Write-Host ("[OK] /api/clients respondeu em " + $clientsElapsedMs + " ms")
Write-Host ("[OK] Cliente smoke em: " + $create.clientDir)
