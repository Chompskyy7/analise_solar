param(
  [Parameter(Mandatory = $true)]
  [string]$RemoteUrl
)

$ErrorActionPreference = "Stop"

function Ensure-Git {
  $git = "C:\Program Files\Git\cmd\git.exe"
  if (-not (Test-Path -LiteralPath $git)) {
    throw "git.exe não encontrado em $git"
  }
  return $git
}

$git = Ensure-Git
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
  & $git remote get-url origin *> $null
  if ($LASTEXITCODE -eq 0) {
    & $git remote set-url origin $RemoteUrl
  } else {
    & $git remote add origin $RemoteUrl
  }

  $branches = @("main", "pr/sprint-1", "pr/sprint-2", "pr/sprint-3")
  foreach ($branch in $branches) {
    & $git push -u origin $branch
  }

  Write-Host "[OK] Branches publicadas:"
  foreach ($branch in $branches) {
    Write-Host "  - $branch"
  }
} finally {
  Pop-Location
}
