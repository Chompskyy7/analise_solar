param(
  [Parameter(Mandatory = $true)]
  [string]$RemoteUrl,
  [string]$BaseBranch = "main"
)

$ErrorActionPreference = "Stop"

function Resolve-ToolPath {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Name
  )
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "$Name não encontrado em $Path"
  }
  return $Path
}

$git = Resolve-ToolPath -Path "C:\Program Files\Git\cmd\git.exe" -Name "git.exe"
$gh = Resolve-ToolPath -Path "C:\Program Files\GitHub CLI\gh.exe" -Name "gh.exe"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
  $publishScript = Join-Path $PSScriptRoot "publish_sprint_branches.ps1"
  if (-not (Test-Path -LiteralPath $publishScript)) {
    throw "Script de publicação não encontrado: $publishScript"
  }

  & $publishScript -RemoteUrl $RemoteUrl

  $templatesPath = Join-Path $repoRoot "docs\pr\PR_TEMPLATES.md"
  if (-not (Test-Path -LiteralPath $templatesPath)) {
    throw "Templates de PR não encontrados: $templatesPath"
  }

  $prDefinitions = @(
    @{ Branch = "pr/sprint-1"; Title = "Sprint 1: consolidar globals.css e schema_version com migração segura" },
    @{ Branch = "pr/sprint-2"; Title = "Sprint 2: observabilidade por tarefa (logs, diagnóstico sanitizado, hash/drift)" },
    @{ Branch = "pr/sprint-3"; Title = "Sprint 3: telemetria opt-in e rollback automático pós-update" }
  )

  foreach ($pr in $prDefinitions) {
    $bodyFile = Join-Path $repoRoot ("docs\pr\" + ($pr.Branch -replace "pr/", "") + ".md")
    if (-not (Test-Path -LiteralPath $bodyFile)) {
      throw "Arquivo de escopo/evidência não encontrado: $bodyFile"
    }

    & $gh pr create `
      --base $BaseBranch `
      --head $pr.Branch `
      --title $pr.Title `
      --body-file $bodyFile
  }

  Write-Host "[OK] PRs criados com sucesso."
} finally {
  Pop-Location
}
