@echo off
title Pipeline Solar Backend

set SCRIPT_DIR=%~dp0
set PYTHON_EXE=%SCRIPT_DIR%..\python\python.exe

if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

cd /d "%SCRIPT_DIR%"
"%PYTHON_EXE%" "%SCRIPT_DIR%backend\server.py"
