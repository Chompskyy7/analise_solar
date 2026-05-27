@echo off
setlocal
title Publicar Release Desktop - Analise Solar Plus

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR:~0,-1%
set BUNDLE_DIR=%SCRIPT_DIR%src-tauri\target\release\bundle
set DEST_DIR=%USERPROFILE%\Desktop\App analise solar Plus v2
set DO_BUILD=1
set RUN_SMOKE=1

if /I "%~1"=="--skip-build" set DO_BUILD=0
if /I "%~1"=="--no-smoke" set RUN_SMOKE=0
if /I "%~2"=="--skip-build" set DO_BUILD=0
if /I "%~2"=="--no-smoke" set RUN_SMOKE=0

if "%DO_BUILD%"=="1" (
  echo [INFO] Executando build completo...
  call "%SCRIPT_DIR%build_desktop_app.bat"
  if errorlevel 1 (
    echo [ERRO] Falha no build.
    exit /b 1
  )
)

if not exist "%BUNDLE_DIR%" (
  echo [ERRO] Bundle nao encontrado em: %BUNDLE_DIR%
  exit /b 1
)

if not exist "%DEST_DIR%" (
  mkdir "%DEST_DIR%"
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$bundle='%BUNDLE_DIR%'; $dst='%DEST_DIR%';" ^
  "$setup = Get-ChildItem -Path (Join-Path $bundle 'nsis') -Filter '*_x64-setup.exe' | Sort-Object LastWriteTime -Descending | Select-Object -First 1;" ^
  "$msi = Get-ChildItem -Path (Join-Path $bundle 'msi') -Filter '*_x64_en-US.msi' | Sort-Object LastWriteTime -Descending | Select-Object -First 1;" ^
  "if(-not $setup -or -not $msi){ throw 'Artefatos de release nao encontrados.' }" ^
  "Copy-Item -LiteralPath $setup.FullName -Destination (Join-Path $dst $setup.Name) -Force;" ^
  "Copy-Item -LiteralPath $msi.FullName -Destination (Join-Path $dst $msi.Name) -Force;" ^
  "Get-ChildItem -Path $dst -File | Where-Object { $_.Extension -in '.exe','.msi' } | Get-FileHash -Algorithm SHA256 | ForEach-Object { '{0}  {1}' -f $_.Hash, $_.Path.Split('\')[-1] } | Set-Content -Path (Join-Path $dst 'SHA256SUMS.txt') -Encoding UTF8;" ^
  "Write-Host '[OK] Release copiado para:' $dst;" ^
  "Get-ChildItem -Path $dst -File | Sort-Object LastWriteTime -Descending | Select-Object -First 6 Name,Length,LastWriteTime"

if errorlevel 1 (
  echo [ERRO] Falha ao publicar release no Desktop.
  exit /b 1
)

if "%RUN_SMOKE%"=="1" (
  echo [INFO] Rodando quality gate - UI e smoke test...
  if "%DO_BUILD%"=="0" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%src-tauri\scripts\quality_gate.ps1" -ProjectRoot "%ROOT_DIR%" -SkipBuild
  ) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%src-tauri\scripts\quality_gate.ps1" -ProjectRoot "%ROOT_DIR%"
  )
  if errorlevel 1 (
    echo [ERRO] Quality gate falhou.
    exit /b 1
  )
)

echo [OK] Publicacao finalizada.
endlocal
