@echo off
title Build Pipeline Solar Backend Sidecar

set SCRIPT_DIR=%~dp0
set PYTHON_EXE=%SCRIPT_DIR%..\python\python.exe
set SIDECAR_EXE=%SCRIPT_DIR%src-tauri\binaries\pipeline-solar-backend-x86_64-pc-windows-msvc.exe

if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

cd /d "%SCRIPT_DIR%"
echo [1/5] Validando dependencias Python no ambiente de build...
"%PYTHON_EXE%" "%SCRIPT_DIR%backend\server.py" --self-check
if errorlevel 1 (
  echo [ERRO] Dependencias Python ausentes ou invalidas no ambiente de build.
  exit /b 1
)

echo [2/5] Encerrando processos do app/backend para evitar arquivo em uso...
taskkill /F /IM pipeline-solar-backend.exe >nul 2>nul
taskkill /F /IM pipeline-solar-backend-x86_64-pc-windows-msvc.exe >nul 2>nul

echo [3/5] Limpando sidecar anterior...
if exist "%SIDECAR_EXE%" del /f /q "%SIDECAR_EXE%" >nul 2>nul

echo [4/5] Empacotando backend sidecar com dependencias...
"%PYTHON_EXE%" -m PyInstaller ^
  --clean ^
  --noconfirm ^
  --onefile ^
  --noconsole ^
  --name pipeline-solar-backend-x86_64-pc-windows-msvc ^
  --distpath src-tauri\binaries ^
  --workpath build\pyinstaller ^
  --specpath build\pyinstaller ^
  --collect-submodules pdfplumber ^
  --collect-submodules openpyxl ^
  --collect-submodules xlrd ^
  --exclude-module pandas.tests ^
  --exclude-module pytest ^
  --collect-data openpyxl ^
  --collect-data pandas ^
  --collect-binaries pandas ^
  --hidden-import pipeline_core ^
  --hidden-import backend.service ^
  --hidden-import pdfplumber ^
  --hidden-import pandas ^
  --hidden-import openpyxl ^
  --hidden-import xlrd ^
  backend\server.py
if errorlevel 1 exit /b 1

if not exist "%SIDECAR_EXE%" (
  echo [ERRO] Sidecar nao foi gerado em: %SIDECAR_EXE%
  exit /b 1
)

echo [5/5] Validando sidecar empacotado...
"%SIDECAR_EXE%" --self-check >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Self-check do sidecar falhou. Pacote pode estar incompleto.
  exit /b 1
)

echo [OK] Sidecar validado: %SIDECAR_EXE%
