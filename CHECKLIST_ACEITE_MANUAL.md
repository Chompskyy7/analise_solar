# Checklist de Aceite Manual - Analise Solar Plus

Use este checklist apos instalar o setup mais recente para validar UX/UI e fluxo real.

## 1) Abertura e fechamento

1. Abrir `Análise Solar Plus` pelo atalho.
2. Confirmar que a janela abre sem travar em "Nao respondendo".
3. Fechar pelo botao `X`.
4. Confirmar que nao ficam processos `analise-solar-plus` e `pipeline-solar-backend`.

## 2) Configuracao basica

1. Ir em `Configuracoes`.
2. Confirmar `Pasta base`, `Downloads` e `Saida`.
3. Salvar e reabrir o app.
4. Confirmar persistencia dos mesmos valores.

## 3) Fluxo operacional

1. Ir em `Executar`.
2. Selecionar cliente e clicar `Criar cliente`.
3. Rodar `Previa`.
4. Rodar `Validacao`.
5. Rodar `Executar`.
6. Confirmar barra/status da tarefa e mensagem final.

## 4) UX/UI visual

1. Validar sidebar fixa com icones e destaque correto da aba ativa.
2. Validar spacing entre botoes (sem elementos colados).
3. Validar leitura de texto (sem mojibake, sem cortes graves).
4. Validar tabela e painel de detalhe sem sobreposicao.
5. Validar tema escuro padrao com contraste adequado.

## 5) Historico e diagnostico

1. Abrir aba `Historico` e clicar `Atualizar`.
2. Abrir aba `Diagnostico` e executar `Diagnosticar`.
3. Confirmar retorno de itens de checagem.

## 6) Reinstalacao/atualizacao

1. Rodar setup novo por cima da versao instalada.
2. Confirmar que abre normalmente apos update.
3. Confirmar que configuracoes do usuario foram preservadas.
