# Aceite Técnico v0.4.0 (Consolidação)

Data da validação: 2026-05-27

## Sprint 1

### Tarefa 1 — Consolidação visual
- `frontend/src/main.tsx` importa apenas `./globals.css`.
- `frontend/src/styles.css` ausente.
- Busca por referência legada:
  - comando: `rg -n "styles\\.css" frontend/src frontend/dist -S`
  - resultado: `NO_STYLES_CSS_REFERENCES`.
- Build de frontend:
  - comando: `npm.cmd run build`
  - resultado: OK (`dist/assets/index-CM4Lj1DX.css`, `dist/assets/index-BizjtHXA.js`).

### Tarefa 2 — Schema versioning
- `backend/service.py` usa `schema_version: 1` em settings/history e migração com `.bak`.
- Testes:
  - `python backend/tests/test_settings_encoding.py` -> OK (6 testes).
  - cobre:
    - migração de legado sem schema com backup `.json.bak`;
    - erro em schema desconhecido sem sobrescrever arquivo.

### Evidência operacional adicional
- `quality_gate.ps1 -SkipBuild` -> OK.
- Smoke de app release abriu janela principal e encerrou sem processos residuais.

## Sprint 2

### Tarefa 3 — Logging estruturado por job
- Estrutura e códigos padronizados implementados em `backend/service.py` + `backend/error_codes.py`.
- Testes:
  - `python backend/tests/test_job_observability.py` -> OK.

### Tarefa 4 — Export de diagnóstico sem sensíveis
- Export por job com sanitização e schema_version no pacote.
- Testes:
  - `python backend/tests/test_job_observability.py` -> OK.

### Tarefa 5 — Hash SHA-256 por job
- Hash determinístico gravado em `history.json` e comparação de drift.
- Testes:
  - `python backend/tests/test_job_observability.py` -> OK.

## Sprint 3

### Tarefa 6 — Telemetria opt-in
- Default desligado e endpoint configurável em settings.
- UI com toggle e disclosure explícito de dados coletados.
- Testes:
  - `python backend/tests/test_telemetry_optin.py` -> OK (6 testes).

### Tarefa 7 — Update channel com rollback automático
- Fluxo de rollback validado com health check forçado:
  - comando:
    - `powershell -NoProfile -ExecutionPolicy Bypass -File src-tauri/scripts/simulate_update_rollback_health_fail.ps1 -ProjectRoot <root>`
  - resultado:
    - `[OK] Rollback automatico disparado.`
    - `[OK] De: 0.2.9 -> 0.3.0`
    - `[OK] Canal: local-installer`
- Ajustes aplicados para estabilidade:
  - persistência imediata de `rollback_notice` no fluxo de rollback;
  - cópia do sidecar para `target/release` no build local;
  - script de simulação com UTF-8 sem BOM e timeout padrão maior.

## Build e artefatos

- Build desktop completo:
  - comando: `build_desktop_app.bat`
  - resultado: OK.
- Artefatos:
  - `src-tauri/target/release/bundle/nsis/Análise Solar Plus_0.3.0_x64-setup.exe`
  - `src-tauri/target/release/bundle/msi/Análise Solar Plus_0.3.0_x64_en-US.msi`

## Nota de processo

- O repositório local não está com fluxo Git remoto habilitado neste ambiente (`git` indisponível no shell atual), então a separação em PRs deve ser feita no ambiente com Git configurado usando este aceite como base.
