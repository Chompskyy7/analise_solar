# Entrega de PRs por Sprint (local)

Este projeto foi inicializado localmente em Git para organizar a entrega por sprint.

## Branches locais criadas
- `pr/sprint-1`
- `pr/sprint-2`
- `pr/sprint-3`

## Commits de referência
- `main`: `chore(repo): importar estado consolidado local v0.3.0`
- `pr/sprint-1`: `docs(sprint-1): escopo e evidências do PR isolado`
- `pr/sprint-2`: `docs(sprint-2): escopo e evidências do PR isolado`
- `pr/sprint-3`: `docs(sprint-3): escopo e evidências do PR isolado`

## Patches gerados
Em `docs/pr/patches/`:
- `0001-docs-sprint-1-escopo-e-evid-ncias-do-PR-isolado.patch`
- `0001-docs-sprint-2-escopo-e-evid-ncias-do-PR-isolado.patch`
- `0001-docs-sprint-3-escopo-e-evid-ncias-do-PR-isolado.patch`

## Publicação quando houver remoto
1. Adicionar remoto:
   - `git remote add origin <url-do-repo>`
2. Enviar branches:
   - `git push -u origin main`
   - `git push -u origin pr/sprint-1`
   - `git push -u origin pr/sprint-2`
   - `git push -u origin pr/sprint-3`
3. Abrir PRs no provedor Git usando as branches acima.

## Observação importante
Como o projeto estava sem histórico Git prévio (`.git` ausente), os PRs locais de sprint foram estruturados com foco em escopo/evidência e transporte (patches). Para diffs retroativos completos por sprint em código, é necessário baseline versionado anterior (ou repositório remoto com histórico pré-consolidação).
