# PR Sprint 3 — Telemetria opt-in + rollback pós-update

## Escopo
- Telemetria de erro opt-in (desligada por padrão), com endpoint configurável e disclosure explícito na UI.
- Rollback automático após update quando `GET /api/health` falha.
- Notificação de rollback exposta pelo backend (`rollbackNotice`) e consumida pelo frontend.
- Estabilização de build/simulação local:
  - sidecar garantido em `target/release`;
  - simulação com escrita UTF-8 sem BOM e timeout adequado.

## Evidências de aceite
- `python backend/tests/test_telemetry_optin.py` -> OK.
- `powershell ... simulate_update_rollback_health_fail.ps1 -ProjectRoot <root>` -> OK:
  - `[OK] Rollback automatico disparado.`
- `quality_gate.ps1 -SkipBuild` -> OK.

## Arquivos principais
- `frontend/src/App.tsx`
- `backend/service.py`
- `backend/telemetry.py`
- `src-tauri/src/lib.rs`
- `src-tauri/scripts/simulate_update_rollback_health_fail.ps1`
- `build_desktop_app.bat`
