param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd("\")
$bundle = Join-Path $root "src-tauri\target\release\bundle"
$nsisDir = Join-Path $bundle "nsis"
$msiDir = Join-Path $bundle "msi"
$sidecar = Join-Path $root "src-tauri\binaries\pipeline-solar-backend-x86_64-pc-windows-msvc.exe"
$nsiScript = Join-Path $root "src-tauri\target\release\nsis\x64\installer.nsi"

if (-not (Test-Path -LiteralPath $sidecar)) {
  throw "[ERRO] Sidecar nao encontrado: $sidecar"
}

$setup = Get-ChildItem -LiteralPath $nsisDir -Filter "*-setup.exe" -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $setup) {
  throw "[ERRO] Instalador NSIS nao encontrado em: $nsisDir"
}

$msi = Get-ChildItem -LiteralPath $msiDir -Filter "*.msi" -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (Test-Path -LiteralPath $nsiScript) {
  $nsiText = Get-Content -LiteralPath $nsiScript -Raw
  if ($nsiText -notmatch [Regex]::Escape($root)) {
    throw "[ERRO] installer.nsi aponta para outro caminho de projeto. Limpe target e gere novo build."
  }
}

Write-Host "[OK] Bundle validado."
Write-Host "NSIS: $($setup.FullName)"
if ($msi) {
  Write-Host "MSI:  $($msi.FullName)"
}
