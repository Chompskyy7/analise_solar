# PR Sprint 1 — Consolidação visual + schema versioning

## Escopo
- Remoção do legado `styles.css` do fluxo ativo.
- `globals.css` como única folha global importada em `frontend/src/main.tsx`.
- Persistência com `schema_version: 1` para `settings.json` e `history.json`.
- Migração automática de JSON legado sem schema com backup `.bak`.
- Erro explícito para schema desconhecido sem sobrescrita silenciosa.

## Evidências de aceite
- `rg -n "styles\\.css" frontend/src frontend/dist -S` -> sem referências.
- `python backend/tests/test_settings_encoding.py` -> OK (migração + `.bak` + schema desconhecido).
- `npm.cmd run build` -> OK.
- `quality_gate.ps1 -SkipBuild` -> OK.

## Arquivos principais
- `frontend/src/main.tsx`
- `frontend/src/globals.css`
- `backend/service.py`
- `backend/tests/test_settings_encoding.py`
