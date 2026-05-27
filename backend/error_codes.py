from __future__ import annotations

"""
Catalogo central de codigos de erro do backend.

Padrao:
- `OK` para execucoes concluidas sem erro.
- `ERR_*` para falhas classificadas.
"""

OK = "OK"
ERR_PERIODO_INVALIDO = "ERR_PERIODO_INVALIDO"
ERR_ARQUIVO_NAO_ENCONTRADO = "ERR_ARQUIVO_NAO_ENCONTRADO"
ERR_PERMISSAO_NEGADA = "ERR_PERMISSAO_NEGADA"
ERR_IMPORT_PIPELINE_CORE = "ERR_IMPORT_PIPELINE_CORE"
ERR_PLANILHA_INVALIDA = "ERR_PLANILHA_INVALIDA"
ERR_VALIDACAO_ENTRADA = "ERR_VALIDACAO_ENTRADA"
ERR_EXECUCAO_CANCELADA = "ERR_EXECUCAO_CANCELADA"
ERR_EXECUCAO_PIPELINE = "ERR_EXECUCAO_PIPELINE"

ERROR_CODE_DOCS: dict[str, str] = {
    OK: "Execucao concluida sem erros.",
    ERR_PERIODO_INVALIDO: "Regra de periodo invalida ou divergente.",
    ERR_ARQUIVO_NAO_ENCONTRADO: "Arquivo de entrada/saida nao encontrado.",
    ERR_PERMISSAO_NEGADA: "Falha de permissao de acesso ao sistema de arquivos.",
    ERR_IMPORT_PIPELINE_CORE: "Falha ao carregar o modulo pipeline_core.",
    ERR_PLANILHA_INVALIDA: "Erro na leitura/geracao de planilhas.",
    ERR_VALIDACAO_ENTRADA: "Payload invalido ou dados obrigatorios ausentes.",
    ERR_EXECUCAO_CANCELADA: "Execucao cancelada.",
    ERR_EXECUCAO_PIPELINE: "Falha generica durante execucao do pipeline.",
}


def classify_error(message: str, cancel_requested: bool = False) -> str:
    text = (message or "").lower()
    if cancel_requested or "cancelad" in text:
        return ERR_EXECUCAO_CANCELADA
    if "periodo" in text and (
        "diverg" in text or "inval" in text or "nao corresponde" in text or "não corresponde" in text
    ):
        return ERR_PERIODO_INVALIDO
    if (
        "nenhum arquivo" in text
        or "nao encontrado" in text
        or "não encontrado" in text
        or "file not found" in text
    ):
        return ERR_ARQUIVO_NAO_ENCONTRADO
    if "permission" in text or "permiss" in text or "acesso negado" in text:
        return ERR_PERMISSAO_NEGADA
    if "pipeline_core" in text:
        return ERR_IMPORT_PIPELINE_CORE
    if "excel" in text or "xlsx" in text or "workbook" in text:
        return ERR_PLANILHA_INVALIDA
    if (
        "informe o nome do cliente" in text
        or "informe o cliente" in text
        or "payload" in text
        or "lista de corre" in text
    ):
        return ERR_VALIDACAO_ENTRADA
    return ERR_EXECUCAO_PIPELINE
