# Pipeline Solar App - Modernizacao Plus v2

## Status atual (2026-05-22)

- Produto: `Analise Solar Plus`
- Versao: `0.3.0`
- Stack desktop: `React + Tauri + sidecar Python`
- Pasta de publicacao: `C:\Users\User\Desktop\App analise solar Plus v2`

## Comando recomendado de release

```bat
cd /d "C:\Users\User\Documents\New project\Pipeline Solar App - Modernizacao Plus v2"
publicar_release_desktop.bat
```

Esse fluxo faz:

1. build completo do backend sidecar;
2. build desktop (Tauri);
3. copia dos instaladores para Desktop;
4. geracao de `SHA256SUMS.txt`;
5. quality gate (testes backend + checks de UI + smoke test).

## Arquitetura resumida

```text
pipeline_core.py        Core legado de extracao e consolidacao
backend/                API local JSON (127.0.0.1:8765)
frontend/               React + Vite + TypeScript
src-tauri/              Shell desktop e empacotamento
```

## Scripts principais

- `build_backend_sidecar.bat`
  - monta `pipeline-solar-backend-x86_64-pc-windows-msvc.exe`
  - roda `--self-check` no backend empacotado
- `build_desktop_app.bat`
  - build sidecar + build tauri
- `publicar_release_desktop.bat`
  - gera release e publica no Desktop
- `src-tauri/scripts/quality_gate.ps1`
  - executa testes backend
  - valida consistencia minima de UI
  - roda smoke test operacional
- `src-tauri/scripts/smoke_test_release.ps1`
  - sobe backend
  - verifica health/settings/clients
  - testa create-client
  - executa preview + preflight
  - dispara pipeline e valida finalizacao de tarefa
  - executa diagnostics
  - abre e fecha app para detectar processo orfao

## Testes backend no gate

- `backend/tests/test_periodo_rule.py`
- `backend/tests/test_settings_encoding.py`
- `backend/tests/test_clients_listing.py`

## Objetivos de estabilidade cobertos

- startup sem import pesado desnecessario em `/api/clients`;
- ausencia de auto-instalacao de dependencias no runtime;
- leitura resiliente de `settings.json` (utf-8-sig/utf-8/cp1252);
- fechamento com cleanup de processos app/backend;
- validacao automatica para reduzir regressao em atualizacao.

## Notas de manutencao

- preservar esta pasta como area de modernizacao isolada;
- nao editar o app original fora desta copia sem decisao explicita;
- publicar sempre via `publicar_release_desktop.bat`;
- manter a versao (`frontend/package.json` + `src-tauri/tauri.conf.json`) alinhada antes de release.
- usar `CHECKLIST_ACEITE_MANUAL.md` no pos-instalacao para validar UX/UI final.
