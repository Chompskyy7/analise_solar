@echo off
title Pipeline Solar Modernizacao

set SCRIPT_DIR=%~dp0

echo Iniciando backend...
start "Pipeline Solar Backend" "%SCRIPT_DIR%start_backend.bat"

if exist "%SCRIPT_DIR%frontend\package.json" (
    echo Iniciando frontend...
    cd /d "%SCRIPT_DIR%frontend"
    npm run dev
) else (
    echo Frontend ainda nao encontrado.
    pause
)
