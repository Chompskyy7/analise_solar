@echo off
title Build Pipeline Solar Desktop

set SCRIPT_DIR=%~dp0
set PATH=%USERPROFILE%\.cargo\bin;%PATH%

cd /d "%SCRIPT_DIR%"
call "%SCRIPT_DIR%build_backend_sidecar.bat"
if errorlevel 1 exit /b 1

cd /d "%SCRIPT_DIR%frontend"
npm.cmd run tauri:build
if errorlevel 1 exit /b 1

set RELEASE_DIR=%SCRIPT_DIR%src-tauri\target\release
set SIDECAR_SRC=%SCRIPT_DIR%src-tauri\binaries\pipeline-solar-backend-x86_64-pc-windows-msvc.exe
if exist "%SIDECAR_SRC%" (
  copy /y "%SIDECAR_SRC%" "%RELEASE_DIR%\pipeline-solar-backend.exe" >nul
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%src-tauri\scripts\verify_bundle_integrity.ps1" -ProjectRoot "%SCRIPT_DIR%"
if errorlevel 1 exit /b 1
