# PR Sprint 2 — Observabilidade por tarefa

## Escopo
- Logging estruturado por job:
  - `job_id`, timestamps início/fim, `error_code` padronizado e stack sanitizado.
- Códigos de erro centralizados em módulo único.
- Export de diagnóstico por tarefa sem dados sensíveis por padrão.
- Hash SHA-256 de saída por job com persistência em histórico para detecção de drift.

## Evidências de aceite
- `python backend/tests/test_job_observability.py` -> OK.
- `python backend/server.py --self-check` -> OK.
- Endpoint de suporte disponível:
  - `POST /api/support/export`.

## Arquivos principais
- `backend/error_codes.py`
- `backend/service.py`
- `backend/server.py`
- `backend/tests/test_job_observability.py`
