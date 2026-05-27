@echo off
setlocal
chcp 65001 >nul

set "ROOT=%~dp0"
set "BUNDLE=%ROOT%src-tauri\target\release\bundle"
set "OUT=%USERPROFILE%\Desktop\App análise solar"
set "VERSION=0.1.0"
set "NSIS=%BUNDLE%\nsis\Pipeline Solar_0.1.0_x64-setup.exe"
set "MSI=%BUNDLE%\msi\Pipeline Solar_0.1.0_x64_en-US.msi"

echo Pipeline Solar - preparo da pasta final de release
echo Destino: %OUT%
echo.

if not exist "%NSIS%" (
  echo [ERRO] Instalador NSIS principal nao encontrado:
  echo %NSIS%
  exit /b 1
)

if not exist "%OUT%" mkdir "%OUT%"
if errorlevel 1 exit /b 1

copy /Y "%NSIS%" "%OUT%\" >nul
if errorlevel 1 exit /b 1

if exist "%MSI%" (
  copy /Y "%MSI%" "%OUT%\" >nul
  if errorlevel 1 exit /b 1
) else (
  echo [AVISO] MSI opcional nao encontrado. A pasta sera montada apenas com o NSIS.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$out=$env:OUT; $version=$env:VERSION; $now=Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'; $files=Get-ChildItem -LiteralPath $out -File | Where-Object { $_.Extension -in '.exe','.msi' } | Sort-Object Name; $hashes=$files | Get-FileHash -Algorithm SHA256 | ForEach-Object { '{0}  {1}' -f $_.Hash, (Split-Path $_.Path -Leaf) }; Set-Content -LiteralPath (Join-Path $out 'SHA256SUMS.txt') -Value $hashes -Encoding UTF8; $manifest=@('Produto: Pipeline Solar','Versao: '+$version,'Gerado em: '+$now,'Pasta: '+$out,'','Arquivos:') + ($files | ForEach-Object { '- '+$_.Name+' ('+$_.Length+' bytes)' }); Set-Content -LiteralPath (Join-Path $out 'MANIFESTO_RELEASE.txt') -Value $manifest -Encoding UTF8; $readme=@('Pipeline Solar - instalacao','','1. Execute Pipeline Solar_0.1.0_x64-setup.exe.','2. Siga o assistente de instalacao do Windows.','3. Ao concluir, abra Pipeline Solar pelo atalho criado no menu Iniciar ou na area de trabalho, se o instalador oferecer essa opcao.','4. Se o Windows SmartScreen bloquear a execucao, confirme que o arquivo veio desta pasta de release e valide o SHA256 em SHA256SUMS.txt antes de continuar.','','Artefato principal: Pipeline Solar_0.1.0_x64-setup.exe','Artefato opcional: Pipeline Solar_0.1.0_x64_en-US.msi','Versao: '+$version,'Gerado em: '+$now); Set-Content -LiteralPath (Join-Path $out 'README_INSTALACAO.txt') -Value $readme -Encoding UTF8"
if errorlevel 1 exit /b 1

echo.
echo Pasta final preparada:
echo %OUT%
echo.
dir "%OUT%"

endlocal
