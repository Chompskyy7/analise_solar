# Analise Solar Plus - Release Rapido

Este fluxo foi criado para facilitar atualizacao futura com validacao automatica.

## Comando unico (recomendado)

```bat
cd /d "C:\Users\User\Documents\New project\Pipeline Solar App - Modernizacao Plus v2"
publicar_release_desktop.bat
```

O comando acima faz:

1. build completo do backend sidecar + app desktop;
2. copia dos instaladores para:
   `C:\Users\User\Desktop\App analise solar Plus v2`;
3. geracao de `SHA256SUMS.txt`;
4. quality gate + smoke test do release.

## O quality gate valida

1. Testes backend:
   - `backend/tests/test_periodo_rule.py`
   - `backend/tests/test_settings_encoding.py`
   - `backend/tests/test_clients_listing.py`
2. Consistencia minima de UI:
   - `main.tsx` importa `globals.css`
   - fontes `Sora` e `DM Mono` em `frontend/index.html`
   - titulo do produto em `index.html`
   - ausencia de import legado de `styles.css`
   - rotina de reconexao e shutdown em `App.tsx`
3. Smoke operacional:
   - sidecar sobe e responde `/api/health`
   - `/api/settings` e `/api/clients` respondem
   - cria cliente de teste via API
   - roda `preview`, `preflight`, `pipeline/run` e valida finalizacao de tarefa
   - roda `diagnostics/run` e valida retorno de itens
   - app desktop abre e fecha sem processos orfaos

## Opcoes uteis

Publicar sem rebuild (usa artefatos ja gerados):

```bat
publicar_release_desktop.bat --skip-build
```

Publicar sem smoke test:

```bat
publicar_release_desktop.bat --no-smoke
```

## Smoke test manual (isolado)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\src-tauri\scripts\smoke_test_release.ps1" -ProjectRoot "."
```
