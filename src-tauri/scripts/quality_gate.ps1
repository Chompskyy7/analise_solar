param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectRoot,
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath ($ProjectRoot.Trim('"').Trim().TrimEnd("\"))).Path.TrimEnd("\")
$frontend = Join-Path $root "frontend"
$appTsx = Join-Path $frontend "src\App.tsx"
$globalsCss = Join-Path $frontend "src\globals.css"
$indexHtml = Join-Path $frontend "index.html"
$mainTsx = Join-Path $frontend "src\main.tsx"
$tauriConf = Join-Path $root "src-tauri\tauri.conf.json"
$smokeScript = Join-Path $root "src-tauri\scripts\smoke_test_release.ps1"

function Assert-Contains {
  param([string]$Path, [string]$Pattern, [string]$Message)
  $hit = Select-String -Path $Path -Pattern $Pattern -SimpleMatch -ErrorAction SilentlyContinue
  if (-not $hit) {
    throw $Message
  }
}

function Assert-NotContainsRegex {
  param([string]$Path, [string]$Pattern, [string]$Message)
  $hit = Select-String -Path $Path -Pattern $Pattern -ErrorAction SilentlyContinue
  if ($hit) {
    throw $Message
  }
}

if (-not $SkipBuild) {
  Push-Location $frontend
  try {
    npm.cmd run build | Out-Host
  } finally {
    Pop-Location
  }
}

# Regressao backend (datas, encoding e listagem leve de clientes)
Push-Location $root
try {
  python backend\tests\test_periodo_rule.py | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Teste backend de periodo falhou." }
  python backend\tests\test_settings_encoding.py | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Teste backend de encoding de settings falhou." }
  python backend\tests\test_clients_listing.py | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Teste backend de listagem de clientes falhou." }
} finally {
  Pop-Location
}

# Regras rápidas de consistência de UI
Assert-Contains -Path $mainTsx -Pattern 'import "./globals.css";' -Message "main.tsx não importa globals.css."
Assert-NotContainsRegex -Path $mainTsx -Pattern "styles\.css" -Message "main.tsx ainda importa styles.css legado."
Assert-Contains -Path $indexHtml -Pattern "family=Sora" -Message "index.html sem fonte Sora."
Assert-Contains -Path $indexHtml -Pattern "family=DM+Mono" -Message "index.html sem fonte DM Mono."
Assert-Contains -Path $indexHtml -Pattern "Solar Plus</title>" -Message "index.html sem titulo correto do produto."
Assert-Contains -Path $globalsCss -Pattern "--bg-base: #0f1117;" -Message "globals.css sem palette base esperada."
Assert-Contains -Path $globalsCss -Pattern "--accent: #f59e0b;" -Message "globals.css sem acento âmbar esperado."
Assert-Contains -Path $appTsx -Pattern "reconnectBackend" -Message "App.tsx sem ação de reconexão."
Assert-Contains -Path $appTsx -Pattern "statusText(apiState)" -Message "App.tsx sem indicador de status de conexão."
Assert-Contains -Path $appTsx -Pattern "requestShutdownOnClose" -Message "App.tsx sem rotina de shutdown no fechamento."
Assert-NotContainsRegex -Path $appTsx -Pattern "ConexÃ£o|ConexÃƒÂ£o|PrÃ©via|PrÃƒÂ©via|ValidaÃ§Ã£o|ValidaÃƒÂ§ÃƒÂ£o|ConfiguraÃ§Ãµes|ConfiguraÃƒÂ§ÃƒÂµes|HistÃ³rico|HistÃƒÂ³rico|DiagnÃ³stico|DiagnÃƒÂ³stico" -Message "App.tsx com texto mojibake."
Assert-NotContainsRegex -Path $tauriConf -Pattern "AnÃ¡lise|AnÃƒÂ¡lise" -Message "tauri.conf.json com nome mojibake."

# Smoke test operacional do release
powershell -NoProfile -ExecutionPolicy Bypass -File $smokeScript -ProjectRoot $root | Out-Host
if ($LASTEXITCODE -ne 0) {
  throw "Smoke test do release falhou."
}

Write-Host "[OK] Quality gate passou."
