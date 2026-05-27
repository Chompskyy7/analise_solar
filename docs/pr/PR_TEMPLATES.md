# Templates de PR por Sprint

## PR 1 — Sprint 1 (Consolidação visual + schema)

**Título sugerido**  
`Sprint 1: consolidar globals.css e schema_version com migração segura`

**Descrição sugerida**
```
## Escopo
- Remove referência legada de styles.css no fluxo ativo.
- Mantém globals.css como única folha global importada.
- Introduz/garante schema_version=1 em settings/history.
- Implementa migração de JSON legado sem schema com backup .bak.
- Garante erro explícito para schema desconhecido sem sobrescrita silenciosa.

## Evidências
- npm.cmd run build -> OK
- python backend/tests/test_settings_encoding.py -> OK
- quality_gate.ps1 -SkipBuild -> OK

## Checklist
- [ ] Sem import de styles.css em frontend/src
- [ ] Startup estável com JSON legado
- [ ] Backup .bak criado na migração
```

## PR 2 — Sprint 2 (Observabilidade)

**Título sugerido**  
`Sprint 2: observabilidade por tarefa (logs, diagnóstico sanitizado, hash/drift)`

**Descrição sugerida**
```
## Escopo
- Logging estruturado por job com código de erro padronizado.
- Export de diagnóstico por tarefa sem dados sensíveis por padrão.
- SHA-256 por saída de job e comparação para detecção de drift.

## Evidências
- python backend/tests/test_job_observability.py -> OK
- python backend/server.py --self-check -> OK

## Checklist
- [ ] Log estruturado consultável por tarefa
- [ ] Export de suporte sem vazamento de dados sensíveis
- [ ] Hash presente em history após execução
```

## PR 3 — Sprint 3 (Telemetria opt-in + rollback)

**Título sugerido**  
`Sprint 3: telemetria opt-in e rollback automático pós-update`

**Descrição sugerida**
```
## Escopo
- Telemetria de erros opt-in (desligada por padrão), endpoint configurável.
- Disclosure explícito dos dados coletados em Configurações.
- Rollback automático quando health check falha após update.
- Notificação de rollback exposta no health e consumida no frontend.
- Estabilização de build local com sidecar no target/release.

## Evidências
- python backend/tests/test_telemetry_optin.py -> OK
- simulate_update_rollback_health_fail.ps1 -> [OK] Rollback automático disparado
- quality_gate.ps1 -SkipBuild -> OK

## Checklist
- [ ] Toggle opt-in visível e funcional
- [ ] Lista de dados coletados exibida antes da ativação
- [ ] Rollback automático validado em simulação
```
