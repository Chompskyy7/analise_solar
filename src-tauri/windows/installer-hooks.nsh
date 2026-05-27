!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Encerrando processos ativos antes da atualizacao..."
  nsExec::ExecToLog 'taskkill /F /IM analise-solar-plus.exe'
  Pop $0
  nsExec::ExecToLog 'taskkill /F /IM pipeline-solar-backend.exe'
  Pop $1

  Sleep 1000
  DetailPrint "Continuando instalacao com pre-check de processos."
!macroend
