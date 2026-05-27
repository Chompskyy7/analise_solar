@echo off
title Pipeline Solar App

set SCRIPT_DIR=%~dp0
set APP=%SCRIPT_DIR%app_gui.py
set PYTHON_EXE=python

python --version >nul 2>&1
if errorlevel 1 (
    if exist "%USERPROFILE%\Documents\New project\python\python.exe" (
        set PYTHON_EXE=%USERPROFILE%\Documents\New project\python\python.exe
    ) else (
        echo ERRO: Python nao encontrado.
        pause
        exit /b 1
    )
)

if not exist "%APP%" (
    echo ERRO: app_gui.py nao encontrado em %SCRIPT_DIR%
    pause
    exit /b 1
)

start "" "%PYTHON_EXE%" "%APP%"
