@echo off
setlocal
chcp 65001 >nul

set "ROOT=%~dp0"
set "BUNDLE=%ROOT%src-tauri\target\release\bundle"
set "NSIS=%BUNDLE%\nsis\Pipeline Solar_0.1.0_x64-setup.exe"
set "MSI=%BUNDLE%\msi\Pipeline Solar_0.1.0_x64_en-US.msi"

echo Pipeline Solar - artefatos de release
echo.
echo Pasta de bundle:
echo %BUNDLE%
echo.

if exist "%NSIS%" (
  echo [NSIS principal]
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:NSIS; $f=Get-Item -LiteralPath $p; $h=Get-FileHash -Algorithm SHA256 -LiteralPath $p; 'Arquivo: '+$f.FullName; 'Tamanho: '+$f.Length+' bytes'; 'Modificado: '+$f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'); 'SHA256: '+$h.Hash"
  echo.
) else (
  echo [ERRO] NSIS principal nao encontrado:
  echo %NSIS%
  echo.
)

if exist "%MSI%" (
  echo [MSI opcional]
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:MSI; $f=Get-Item -LiteralPath $p; $h=Get-FileHash -Algorithm SHA256 -LiteralPath $p; 'Arquivo: '+$f.FullName; 'Tamanho: '+$f.Length+' bytes'; 'Modificado: '+$f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'); 'SHA256: '+$h.Hash"
  echo.
) else (
  echo [AVISO] MSI opcional nao encontrado:
  echo %MSI%
  echo.
)

endlocal
