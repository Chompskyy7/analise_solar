"""
Pipeline de Energia Solar - v10
===============================
Busca automaticamente os arquivos no drive H: pelo nome do cliente, cria a
estrutura do cliente, importa downloads com prévia/quarentena e gera XLSX com
aba Base_IA.

Estrutura esperada:
  H:/Projetos/Projetos 2026 Gera+/Analise de geracao/
  └── NomeCliente/
      ├── Contas/   <- PDFs das faturas
      └── Dados/    <- XLSXs de geracao

Uso:
    python pipeline_energia.py
    python pipeline_energia.py --cliente "Joao"
    python pipeline_energia.py --cliente "Joao" --importar-baixados
"""

import sys
import re
import argparse
import shutil
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(r"H:\.shortcut-targets-by-id\1l0UkwSici0Ob1UCNelRbz0dA6eyg3kmm\Projetos\Projetos 2026 Gera+\Analise de geração")

import pdfplumber
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


# =============================================================================
# EXTRACAO DE FATURAS PDF
# =============================================================================

def _extrair_pdf(path_pdf: Path) -> dict:
    with pdfplumber.open(path_pdf) as pdf:
        texto = "".join(p.extract_text() or "" for p in pdf.pages)

    mes_ref = None
    m = re.search(r'\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[/\s]+(\d{4})\b', texto, re.IGNORECASE)
    if m:
        mes_ref = f"{m.group(1).upper()}/{m.group(2)}"

    leitura_por_medidor = False
    medidor = re.search(
        r'^\s*\d{8,12}\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+\d{1,3}\b',
        texto,
        re.MULTILINE,
    )
    leit_atual = leit_anterior = None
    if medidor:
        leit_atual = datetime.strptime(medidor.group(1), "%d/%m/%Y")
        leit_anterior = datetime.strptime(medidor.group(2), "%d/%m/%Y")
        leitura_por_medidor = True

    datas = re.findall(r'\b(\d{2}/\d{2}/\d{4})\b', texto)
    candidatas, seen = [], set()
    for d in datas:
        try:
            dt = datetime.strptime(d, "%d/%m/%Y")
            if dt.year >= 2024 and dt not in seen:
                seen.add(dt)
                candidatas.append(dt)
        except ValueError:
            pass

    if not leitura_por_medidor:
        for i in range(len(candidatas) - 1):
            diff = abs((candidatas[i] - candidatas[i + 1]).days)
            if 20 <= diff <= 40:
                if candidatas[i] > candidatas[i + 1]:
                    leit_atual, leit_anterior = candidatas[i], candidatas[i + 1]
                else:
                    leit_atual, leit_anterior = candidatas[i + 1], candidatas[i]
                break

    # Formato 1: unico (residencial/baixa tensao)
    # Usa \S+ como coringa para aceitar variações como unico, UNICO e ÚNICO.
    ma = re.search(
        r'Energia Ativa\s*[- ]\s*kWh\s+\S+\s+[\d.]+\s+[\d.]+\s+[\d,]+\s+([\d.]+(?:,\d+)?)',
        texto,
        re.IGNORECASE
    )
    mi = re.search(
        r'Energia Injetada(?:\s*[- ]\s*kWh)?\s+\S+\s+[\d.]+\s+[\d.]+\s+[\d,]+\s+([\d.]+(?:,\d+)?)',
        texto,
        re.IGNORECASE
    )

    def _parse_milhar(v):
        return int(float(v.replace(".", "").replace(",", ".")))

    energia_ativa = _parse_milhar(ma.group(1)) if ma else None
    energia_injetada = _parse_milhar(mi.group(1)) if mi else None

    # Formato 2: Ponta + Fora Ponta (A4 trifasico)
    # coluna final pode ter ponto como separador de milhar ex: 10.213
    if energia_ativa is None:
        pontas = re.findall(
            r'Energia Ativa\s*-\s*kWh\s+(?:Ponta|Fora\s+Ponta)\s+\d+\s+\d+\s+[\d,]+\s+([\d.]+)',
            texto,
            re.IGNORECASE
        )
        if pontas:
            energia_ativa = sum(_parse_milhar(v) for v in pontas)

    if energia_injetada is None:
        inj = re.findall(
            r'Energia Injetada\s*-\s*k[Ww]\s+(?:Ponta|Fora\s+Ponta)\s+\d+\s+\d+\s+[\d,]+\s+([\d.]+)',
            texto,
            re.IGNORECASE
        )
        if inj:
            energia_injetada = sum(_parse_milhar(v) for v in inj)

    periodo = None
    if leit_anterior and leit_atual:
        fim = leit_atual - timedelta(days=1)
        periodo = f"{leit_anterior.strftime('%d/%m/%Y')} - {fim.strftime('%d/%m/%Y')}"

    return {
        "mes":               mes_ref or path_pdf.stem,
        "periodo":           periodo,
        "leitura_anterior":  leit_anterior.strftime("%d/%m/%Y") if leit_anterior else None,
        "leitura_atual":     leit_atual.strftime("%d/%m/%Y")    if leit_atual    else None,
        "energia_ativa_kwh": energia_ativa,
        "energia_injetada_kwh": energia_injetada,
    }

_MESES_REF = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}
_MESES_REF_REV = {v: k for k, v in _MESES_REF.items()}

def _parse_data_br(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(str(valor).strip(), "%d/%m/%Y")
    except ValueError:
        return None

def _chave_ordenacao_fatura(fat: dict):
    dt = _parse_data_br(fat.get("leitura_anterior"))
    if dt:
        return (0, dt)

    periodo = fat.get("periodo") or ""
    m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", periodo)
    if m:
        dt = _parse_data_br(m.group(1))
        if dt:
            return (0, dt)

    mes = str(fat.get("mes") or "").upper()
    m = re.search(r"\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[/\s]+(\d{4})\b", mes)
    if m:
        return (0, datetime(int(m.group(2)), _MESES_REF[m.group(1)], 1))

    return (1, datetime.max)

def _data_mes_ref(valor):
    mes = str(valor or "").upper()
    m = re.search(r"\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[/\s]+(\d{4})\b", mes)
    if not m:
        return None
    return datetime(int(m.group(2)), _MESES_REF[m.group(1)], 1)

def _mes_ref_por_inicio_periodo(inicio: datetime) -> str:
    mes = inicio.month
    ano = inicio.year
    return f"{_MESES_REF_REV[mes]}/{ano}"

def _adicionar_mes(dt: datetime) -> datetime:
    ano = dt.year
    mes = dt.month + 1
    if mes == 13:
        mes = 1
        ano += 1
    prox_ano = ano + (1 if mes == 12 else 0)
    prox_mes = 1 if mes == 12 else mes + 1
    ultimo_dia = (datetime(prox_ano, prox_mes, 1) - timedelta(days=1)).day
    return datetime(ano, mes, min(dt.day, ultimo_dia))

def _datas_periodo_fatura(fat: dict):
    inicio = _parse_data_br(fat.get("leitura_anterior"))
    atual = _parse_data_br(fat.get("leitura_atual"))
    if inicio and atual:
        return inicio, atual

    periodo = fat.get("periodo") or ""
    datas = re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", periodo)
    if len(datas) >= 2:
        inicio = _parse_data_br(datas[0])
        fim = _parse_data_br(datas[1])
        if inicio and fim:
            return inicio, fim + timedelta(days=1)

    return inicio, atual

def _fim_periodo_fatura(fat: dict):
    fim = _parse_data_br(fat.get("data_fim_periodo"))
    if fim:
        return fim

    periodo = fat.get("periodo") or ""
    datas = re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", periodo)
    if len(datas) >= 2:
        fim = _parse_data_br(datas[1])
        if fim:
            return fim

    _, atual = _datas_periodo_fatura(fat)
    return atual - timedelta(days=1) if atual else None

def _fatura_periodo_vazio(inicio: datetime, atual: datetime) -> dict:
    fim = atual - timedelta(days=1)
    return {
        "mes": _mes_ref_por_inicio_periodo(inicio),
        "periodo": f"{inicio.strftime('%d/%m/%Y')} - {fim.strftime('%d/%m/%Y')}",
        "leitura_anterior": inicio.strftime("%d/%m/%Y"),
        "leitura_atual": atual.strftime("%d/%m/%Y"),
        "energia_ativa_kwh": None,
        "energia_injetada_kwh": None,
    }

def _copiar_valores_fatura(destino: dict, origem: dict) -> bool:
    copiou = False
    for campo in ("energia_ativa_kwh", "energia_injetada_kwh"):
        if destino.get(campo) is None and origem.get(campo) is not None:
            destino[campo] = origem.get(campo)
            copiou = True
    return copiou

def _buscar_fatura_sem_datas(sem_datas: list, usados: set, inicio: datetime):
    mes_periodo = datetime(inicio.year, inicio.month, 1)
    mes_ref_conta = _adicionar_mes(mes_periodo)
    for idx, fat in enumerate(sem_datas):
        if idx in usados:
            continue
        mes_fat = _data_mes_ref(fat.get("mes"))
        if mes_fat in (mes_periodo, mes_ref_conta):
            return idx, fat
    return None, None

def _aplicar_regra_periodo(fat: dict) -> None:
    inicio, atual = _datas_periodo_fatura(fat)
    if not inicio or not atual:
        return
    fim = atual - timedelta(days=1)
    fat["leitura_anterior"] = inicio.strftime("%d/%m/%Y")
    fat["leitura_atual"] = atual.strftime("%d/%m/%Y")
    fat["data_fim_periodo"] = fim.strftime("%d/%m/%Y")
    fat["periodo"] = f"{inicio.strftime('%d/%m/%Y')} - {fim.strftime('%d/%m/%Y')}"
    if atual <= inicio:
        fat["period_rule_warning"] = "PERIODO_SAME_DAY_OR_INVERTED"

def _normalizar_faturas_por_periodo(faturas: list) -> list:
    ordenadas = [dict(fat) for fat in sorted(faturas, key=_chave_ordenacao_fatura)]

    for fat in ordenadas:
        inicio, atual = _datas_periodo_fatura(fat)
        if inicio and atual:
            _aplicar_regra_periodo(fat)
            if not _data_mes_ref(fat.get("mes")):
                fat["mes"] = _mes_ref_por_inicio_periodo(inicio)

    completas = []
    com_datas = []
    sem_datas = []
    for fat in ordenadas:
        inicio, atual = _datas_periodo_fatura(fat)
        if inicio and atual:
            com_datas.append((inicio, atual, fat))
        else:
            sem_datas.append(fat)

    usados_sem_datas = set()
    com_datas.sort(key=lambda item: item[0])
    for idx, (inicio, atual, fat) in enumerate(com_datas):
        idx_sem, fat_sem = _buscar_fatura_sem_datas(sem_datas, usados_sem_datas, inicio)
        if fat_sem and _copiar_valores_fatura(fat, fat_sem):
            usados_sem_datas.add(idx_sem)
        _aplicar_regra_periodo(fat)
        completas.append(fat)
        if idx + 1 >= len(com_datas):
            continue

        prox_inicio = com_datas[idx + 1][0]
        cursor = atual
        while cursor and prox_inicio and (prox_inicio - cursor).days >= 20:
            prox_cursor = prox_inicio
            if (prox_inicio - cursor).days > 45:
                prox_cursor = min(_adicionar_mes(cursor), prox_inicio)
            fat_vazia = _fatura_periodo_vazio(cursor, prox_cursor)
            idx_sem, fat_sem = _buscar_fatura_sem_datas(sem_datas, usados_sem_datas, cursor)
            if fat_sem and _copiar_valores_fatura(fat_vazia, fat_sem):
                usados_sem_datas.add(idx_sem)
            _aplicar_regra_periodo(fat_vazia)
            completas.append(fat_vazia)
            cursor = prox_cursor

    completas.extend(fat for idx, fat in enumerate(sem_datas) if idx not in usados_sem_datas)
    return sorted(completas, key=_chave_ordenacao_fatura)

def extrair_faturas(paths: list) -> list:
    resultados = []
    for p in paths:
        print(f"  [fatura] {p.name}")
        try:
            fat = _extrair_pdf(p)
            fat["fonte_arquivo"] = p.name
            resultados.append(fat)
        except Exception as e:
            print(f"    erro: {e}")
    return _normalizar_faturas_por_periodo(resultados)


# =============================================================================
# EXTRACAO DE GERACAO XLSX
# =============================================================================

def _to_float(v):
    if pd.isna(v):
        return None
    txt = str(v).replace("\xa0", " ").replace("\u202f", " ").strip()
    txt = re.sub(r"\s+", "", txt)
    if not txt:
        return None
    if "," in txt and "." in txt:
        if txt.rfind(",") > txt.rfind("."):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    else:
        txt = txt.replace(",", ".")
    try:
        return float(txt)
    except:
        return None

def _limpar_texto(v) -> str:
    if pd.isna(v):
        return ""
    txt = str(v).replace("\xa0", " ").replace("\u202f", " ").strip()
    return re.sub(r"\s+", " ", txt)

def _normalizar_texto(v) -> str:
    txt = _limpar_texto(v)
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return txt.casefold()

def _parse_data(v, dayfirst: bool = True):
    if isinstance(v, (datetime, pd.Timestamp)):
        return pd.to_datetime(v)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            return pd.to_datetime(v, unit="D", origin="1899-12-30")
        except:
            pass
    txt = _limpar_texto(v)
    if not txt:
        return pd.NaT
    if re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", txt):
        return pd.to_datetime(txt, dayfirst=False, errors="coerce")
    if re.fullmatch(r"\d+(?:[.,]\d+)?", txt):
        try:
            return pd.to_datetime(float(txt.replace(",", ".")), unit="D", origin="1899-12-30")
        except:
            pass
    return pd.to_datetime(txt, dayfirst=dayfirst, errors="coerce")

def _coluna_por_texto(df, *fragmentos):
    for col in df.columns:
        texto = _normalizar_texto(col)
        if all(fragmento in texto for fragmento in fragmentos):
            return col
    return None

def _fmt_asconavieta(df, nome=None):
    col_data = _coluna_por_texto(df, "tempo atualizado")
    col_kwh = _coluna_por_texto(df, "hoje", "producao", "kwh")
    if col_data and col_kwh:
        rows = []
        for _, row in df.iterrows():
            dt = _parse_data(row[col_data], dayfirst=True)
            g = _to_float(row[col_kwh])
            if pd.notna(dt) and g is not None:
                rows.append({"data": dt, "kwh": g})
        return rows or None

    header_row = None
    data_col = None
    kwh_col = None
    for row_idx in range(df.shape[0]):
        valores = [_normalizar_texto(v) for v in df.iloc[row_idx].tolist()]
        for col_idx, valor in enumerate(valores):
            if "tempo atualizado" in valor:
                data_col = col_idx
            if "hoje" in valor and "producao" in valor and "kwh" in valor:
                kwh_col = col_idx
        if data_col is not None and kwh_col is not None:
            header_row = row_idx
            break

    if header_row is None:
        return None

    rows = []
    for row_idx in range(header_row + 1, df.shape[0]):
        raw_data = df.iloc[row_idx, data_col]
        raw_kwh = df.iloc[row_idx, kwh_col]
        dt = _parse_data(raw_data, dayfirst=True)
        g = _to_float(raw_kwh)
        if pd.notna(dt) and g is not None:
            rows.append({"data": dt, "kwh": g})
    return rows or None

def _fmt_A(df, nome):
    col = _coluna_por_texto(df, "rendimento", "inversor")
    if not col: return None
    rows = []
    for _, row in df.iterrows():
        dt = _parse_data(row[df.columns[0]], dayfirst=True)
        g  = _to_float(row[col])
        if pd.notna(dt) and g is not None:
            rows.append({"data": dt, "kwh": g})
    return rows or None

def _fmt_C(df, nome):
    col = _coluna_por_texto(df, "diaria")
    if not col: return None
    rows = []
    for _, row in df.iterrows():
        dt = _parse_data(row[df.columns[0]], dayfirst=True)
        g  = _to_float(row[col])
        if pd.notna(dt) and g is not None: rows.append({"data": dt, "kwh": g})
    return rows or None

def _fmt_D(df, nome):
    col = _coluna_por_texto(df, "solar", "energia")
    if not col: return None
    rows = []
    for _, row in df.iterrows():
        dt = _parse_data(row[df.columns[0]], dayfirst=True)
        g  = _to_float(row[col])
        if pd.notna(dt) and g is not None: rows.append({"data": dt, "kwh": g})
    return rows or None

def _fmt_consolidado(df_raw):
    rows = []
    for col_idx in range(0, df_raw.shape[1], 3):
        for row_idx in range(2, df_raw.shape[0]):
            raw_data = df_raw.iloc[row_idx, col_idx]
            raw_kwh  = df_raw.iloc[row_idx, col_idx + 1] if col_idx + 1 < df_raw.shape[1] else None
            if pd.isna(raw_data) or pd.isna(raw_kwh): continue
            try:
                dt = _parse_data(raw_data, dayfirst=True)
                g  = _to_float(raw_kwh)
                if pd.notna(dt) and g is not None:
                    rows.append({"data": dt, "kwh": g})
            except: continue
    return rows or None

def _fmt_power_station_chart(df_raw):
    header_row = None
    data_col = None
    kwh_col = None

    for row_idx in range(df_raw.shape[0]):
        valores = [_normalizar_texto(v) for v in df_raw.iloc[row_idx].tolist()]
        for col_idx, valor in enumerate(valores):
            if valor == "time":
                data_col = col_idx
            if "yield" in valor and "kwh" in valor:
                kwh_col = col_idx
        if data_col is not None and kwh_col is not None:
            header_row = row_idx
            break

    if header_row is None:
        return None

    rows = []
    for row_idx in range(header_row + 1, df_raw.shape[0]):
        raw_data = df_raw.iloc[row_idx, data_col]
        raw_kwh = df_raw.iloc[row_idx, kwh_col]
        dt = _parse_data(raw_data, dayfirst=True)
        g = _to_float(raw_kwh)
        if pd.notna(dt) and g is not None:
            rows.append({"data": dt, "kwh": g})

    return rows or None

def _processar_xlsx(path: Path) -> list:
    engine = "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"
    try:
        xf_ctx = pd.ExcelFile(path, engine=engine)
    except Exception as e:
        print(f"    erro ao abrir: {e}"); return []

    with xf_ctx as xf:
        for sh in xf.sheet_names:
            for hr in [0, 1]:
                try:
                    df = pd.read_excel(path, sheet_name=sh, header=hr, engine=engine)
                except: continue
                for fn in [_fmt_asconavieta, _fmt_A, _fmt_C, _fmt_D]:
                    r = fn(df, path.name)
                    if r: return r
            try:
                df_raw = pd.read_excel(path, sheet_name=sh, header=None, engine=engine)
                r = _fmt_asconavieta(df_raw)
                if r: return r
                r = _fmt_power_station_chart(df_raw)
                if r: return r
                r = _fmt_consolidado(df_raw)
                if r: return r
            except: pass

    return []

def extrair_geracao(paths: list, retornar_detalhes: bool = False):
    todos = []
    detalhes = []
    for p in paths:
        print(f"  [geracao] {p.name}")
        try:
            rows = _processar_xlsx(p)
            if rows:
                for row in rows:
                    row["fonte_arquivo"] = p.name
                todos.extend(rows)
                detalhes.append({"arquivo": p, "linhas": rows, "ok": True})
            else:
                detalhes.append({"arquivo": p, "linhas": [], "ok": False})
                print(f"    formato nao reconhecido")
        except Exception as e:
            detalhes.append({"arquivo": p, "linhas": [], "ok": False, "erro": str(e)})
            print(f"    erro: {e}")
    if retornar_detalhes:
        return todos, detalhes
    return todos

def _label_mes(dt: datetime) -> str:
    return f"{_MESES_REF_REV[dt.month].lower()}/{dt.year}"

def _meses_fatura(faturas: list) -> list:
    meses = []
    for fat in faturas:
        inicio, _ = _datas_periodo_fatura(fat)
        if inicio:
            meses.append(_label_mes(inicio))
            continue
        mes_ref = _data_mes_ref(fat.get("mes"))
        if mes_ref:
            meses.append(_label_mes(mes_ref))
    return meses

def _meses_geracao_por_arquivo(detalhes_geracao: list) -> dict:
    por_arquivo = {}
    for item in detalhes_geracao:
        meses = set()
        for row in item.get("linhas") or []:
            dt = row.get("data")
            if pd.notna(dt):
                meses.add(_label_mes(pd.to_datetime(dt).to_pydatetime()))
        por_arquivo[item["arquivo"]] = sorted(meses)
    return por_arquivo

def diagnosticar_conjunto(pdf_paths: list, xlsx_paths: list, faturas: list, detalhes_geracao: list):
    print("\nDiagnostico do conjunto")
    print(f"  PDFs lidos              : {len(pdf_paths)}")
    print(f"  Faturas extraidas       : {len(faturas)}")
    print(f"  Arquivos de geracao     : {len(xlsx_paths)}")

    chaves_fatura = {}
    sem_periodo = 0
    for fat in faturas:
        inicio, atual = _datas_periodo_fatura(fat)
        if fat.get("period_rule_warning") or (inicio and atual and atual <= inicio):
            print(f"  AVISO: regra de periodo invalida em {fat.get('fonte_arquivo') or fat.get('mes') or 'fatura'} ({fat.get('leitura_anterior')} -> {fat.get('leitura_atual')})")
        if inicio and atual:
            chave = f"{inicio.strftime('%d/%m/%Y')} - {(atual - timedelta(days=1)).strftime('%d/%m/%Y')}"
        else:
            chave = str(fat.get("mes") or "").strip()
        if not chave:
            sem_periodo += 1
            continue
        chaves_fatura.setdefault(chave, 0)
        chaves_fatura[chave] += 1

    duplicadas_fatura = {k: v for k, v in chaves_fatura.items() if v > 1}
    if duplicadas_fatura:
        for periodo, qtd in duplicadas_fatura.items():
            print(f"  AVISO: fatura duplicada para {periodo}: {qtd} ocorrencias")
    if sem_periodo:
        print(f"  AVISO: {sem_periodo} fatura(s) sem periodo detectado")

    meses_por_arquivo = _meses_geracao_por_arquivo(detalhes_geracao)
    arquivos_sem_geracao = [item for item in detalhes_geracao if not item.get("ok")]
    for item in arquivos_sem_geracao:
        erro = item.get("erro")
        sufixo = f" ({erro})" if erro else ""
        print(f"  AVISO: geracao nao reconhecida em {item['arquivo'].name}{sufixo}")

    arquivos_por_mes = {}
    for arquivo, meses in meses_por_arquivo.items():
        if not meses:
            continue
        for mes in meses:
            arquivos_por_mes.setdefault(mes, []).append(arquivo.name)

    for mes, arquivos in sorted(arquivos_por_mes.items()):
        if len(arquivos) > 1:
            print(f"  AVISO: geracao duplicada/sobreposta para {mes}: {len(arquivos)} arquivos")

    meses_fatura = set(_meses_fatura(faturas))
    meses_geracao = set(arquivos_por_mes.keys())
    if meses_fatura and meses_geracao:
        faltando = sorted(meses_fatura - meses_geracao)
        extras = sorted(meses_geracao - meses_fatura)
        if faltando:
            print(f"  AVISO: sem geracao detectada para: {', '.join(faltando)}")
        if extras:
            print(f"  AVISO: geracao sem fatura correspondente: {', '.join(extras)}")

    if len(pdf_paths) != len(xlsx_paths):
        print(f"  AVISO: quantidade diferente de PDFs ({len(pdf_paths)}) e arquivos de geracao ({len(xlsx_paths)})")


# =============================================================================
# COLETA DE ARQUIVOS
# =============================================================================

def coletar(pasta: Path, exts: tuple) -> list:
    resultado = []
    for ext in exts:
        resultado.extend(p for p in sorted(pasta.glob(f"*{ext}")) if not _ignorar_planilha(p))
    return resultado

def coletar_com_fallback(pasta_cliente: Path, pasta_padrao: Path, exts: tuple) -> tuple[list, str]:
    arquivos = coletar(pasta_padrao, exts)
    if arquivos:
        return arquivos, str(pasta_padrao)

    encontrados = {}
    for ext in exts:
        for path in sorted(pasta_cliente.rglob(f"*{ext}")):
            if not path.is_file() or _ignorar_planilha(path):
                continue
            if QUARENTENA_IMPORTADOS in path.parts:
                continue
            if path.parent == pasta_cliente:
                continue
            encontrados[str(path.resolve()).lower()] = path

    return list(encontrados.values()), f"subpastas de {pasta_cliente}"

def _ignorar_planilha(path: Path) -> bool:
    nome = path.name.lower()
    if nome.startswith("~$"):
        return True
    if path.suffix.lower() not in EXTS_GERACAO:
        return False
    ignorar_por_nome = (
        "analise",
        "análise",
        "dados ia -",
        "importacao downloads",
        "importação downloads",
    )
    return any(item in nome for item in ignorar_por_nome)


# =============================================================================
# ASSISTENTE DE TRIAGEM DOS DOWNLOADS
# =============================================================================

DOWNLOADS_PADRAO = Path.home() / "Downloads"
EXTS_FATURAS = (".pdf",)
EXTS_GERACAO = (".xlsx", ".xls")
QUARENTENA_IMPORTADOS = "_importados_pipeline_solar"

def _arquivo_recente(path: Path, dias: int) -> bool:
    if dias <= 0:
        return True
    limite = datetime.now().timestamp() - (dias * 24 * 60 * 60)
    return path.stat().st_mtime >= limite

def _nome_livre(destino: Path) -> Path:
    if not destino.exists():
        return destino
    stem = destino.stem
    suffix = destino.suffix
    for i in range(2, 1000):
        candidato = destino.with_name(f"{stem} ({i}){suffix}")
        if not candidato.exists():
            return candidato
    raise RuntimeError(f"Nao foi possivel criar nome livre para {destino.name}")

def _coletar_baixados(origem: Path, dias: int) -> tuple[list, list]:
    if not origem.exists():
        return [], []
    arquivos = [p for p in origem.iterdir() if p.is_file() and _arquivo_recente(p, dias)]
    pdfs = sorted((p for p in arquivos if p.suffix.lower() in EXTS_FATURAS), key=lambda p: p.stat().st_mtime)
    planilhas = sorted((p for p in arquivos if p.suffix.lower() in EXTS_GERACAO and not _ignorar_planilha(p)), key=lambda p: p.stat().st_mtime)
    return pdfs, planilhas

def _mostrar_previa_importacao(nome_cliente: str, origem: Path, pdfs: list, planilhas: list):
    print("\nPrevia da importacao")
    print(f"  Cliente : {nome_cliente}")
    print(f"  Origem  : {origem}")
    print(f"  Faturas : {len(pdfs)}")
    for p in pdfs:
        print(f"    - {p.name}")
    print(f"  Geracao : {len(planilhas)}")
    for p in planilhas:
        print(f"    - {p.name}")
    print(f"  Quarentena apos copiar: {origem / QUARENTENA_IMPORTADOS / nome_cliente}")

def _confirmar_importacao() -> bool:
    resposta = input("\nConfirmar importacao e mover originais para quarentena? [S/N]: ").strip().lower()
    return resposta in ("s", "sim", "y", "yes")

def _mover_para_quarentena(origem: Path, destino_dir: Path) -> Path:
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = _nome_livre(destino_dir / origem.name)
    shutil.move(str(origem), str(destino))
    return destino

def _copiar_para_pasta(arquivos: list, destino_dir: Path, categoria: str, quarentena_dir: Path) -> tuple[int, int]:
    destino_dir.mkdir(parents=True, exist_ok=True)
    copiados = 0
    movidos = 0
    for origem in arquivos:
        destino = _nome_livre(destino_dir / origem.name)
        shutil.copy2(origem, destino)
        copiados += 1
        try:
            quarentena = _mover_para_quarentena(origem, quarentena_dir)
            movidos += 1
            print(f"  [{categoria}] {origem.name} -> {destino_dir.name} | quarentena: {quarentena.name}")
        except Exception as e:
            print(f"  [{categoria}] {origem.name} -> {destino_dir.name} | aviso: nao movido para quarentena ({e})")
    return copiados, movidos

def importar_baixados(pasta_cliente: Path, origem: Path, dias: int, confirmar: bool = True) -> tuple[int, int, int, bool]:
    pdfs, planilhas = _coletar_baixados(origem, dias)
    if not pdfs and not planilhas:
        print("  Nenhum arquivo recente encontrado para importar.")
        return 0, 0, 0, True

    if confirmar:
        _mostrar_previa_importacao(pasta_cliente.name, origem, pdfs, planilhas)
        if not _confirmar_importacao():
            print("  Importacao cancelada pelo usuario.")
            return 0, 0, 0, False

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    quarentena_dir = origem / QUARENTENA_IMPORTADOS / pasta_cliente.name / ts
    qtd_pdfs, mov_pdfs = _copiar_para_pasta(pdfs, pasta_cliente / "Contas", "fatura", quarentena_dir)
    qtd_planilhas, mov_planilhas = _copiar_para_pasta(planilhas, pasta_cliente / "Dados", "geracao", quarentena_dir)

    return qtd_pdfs, qtd_planilhas, mov_pdfs + mov_planilhas, True

def listar_clientes(filtro: str = "") -> list:
    if not BASE_DIR.exists():
        return []
    filtro_norm = filtro.strip().lower()
    clientes = [p.name for p in BASE_DIR.iterdir() if p.is_dir()]
    if filtro_norm:
        clientes = [c for c in clientes if filtro_norm in c.lower()]
    return sorted(clientes)

def preparar_pasta_cliente(nome_cliente: str) -> tuple[Path, Path, Path, bool]:
    pasta_cliente = BASE_DIR / nome_cliente
    ja_existia = pasta_cliente.exists()
    pdf_dir = pasta_cliente / "Contas"
    xlsx_dir = pasta_cliente / "Dados"

    if not BASE_DIR.exists():
        raise FileNotFoundError(f"Diretorio base nao encontrado: {BASE_DIR}")

    pasta_cliente.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    xlsx_dir.mkdir(parents=True, exist_ok=True)

    return pasta_cliente, pdf_dir, xlsx_dir, ja_existia


# =============================================================================
# SALVA XLSX FINAL — preenche template exato (Planilha 1 + Planilha2)
# =============================================================================

# Ordem dos 12 meses no template (agosto a julho)
# Planilha 1: col de data (ímpar A,C,E...) e col de kWh (par B,D,F...)
_MES_ORDEM = [8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7]

# col de kWh para cada mês em Planilha 1 (índice 1-based)
_MES_KWH_COL = {m: 2 + i * 2 for i, m in enumerate(_MES_ORDEM)}   # B=2,D=4,...X=24
_MES_DAT_COL = {m: 1 + i * 2 for i, m in enumerate(_MES_ORDEM)}   # A=1,C=3,...W=23

# Nome do mês em português
_NOMES_MES = {
    1:"JANEIRO",2:"FEVEREIRO",3:"MARÇO",4:"ABRIL",5:"MAIO",6:"JUNHO",
    7:"JULHO",8:"AGOSTO",9:"SETEMBRO",10:"OUTUBRO",11:"NOVEMBRO",12:"DEZEMBRO"
}


def _set(ws, row, col, value, fmt=None, bold=False, align=None, fill=None, font_color="000000"):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(name="Calibri", size=11, bold=bold, color=font_color)
    if align:
        c.alignment = Alignment(horizontal=align, vertical="center")
    if fill:
        c.fill = PatternFill("solid", start_color=fill)
    if fmt:
        c.number_format = fmt


def _salvar_xlsx_template_planilha12(faturas: list, geracao_diaria: list, out: Path):
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    # =========================================================
    # PLANILHA 1  —  geração diária por mês (colunas duplas)
    # =========================================================
    ws1 = wb.active
    ws1.title = "Planilha 1"

    # Agrupa geração diária por mês
    from collections import defaultdict
    mes_dias = defaultdict(list)   # (ano, mes) -> [(data, kwh), ...]
    if geracao_diaria:
        df_g = pd.DataFrame(geracao_diaria)
        df_g["data"] = pd.to_datetime(df_g["data"])
        df_g = df_g.sort_values("data")
        for r in df_g.itertuples():
            mes_dias[(r.data.year, r.data.month)].append((r.data, r.kwh))

    # Determina ano de referência para montar as 12 colunas
    # Usa as faturas ou os dados de geração para descobrir o ano base
    if faturas:
        # Primeiro mês da fatura determina o ano base de ago
        primeiro = faturas[0]
        if primeiro.get("leitura_anterior"):
            try:
                d = datetime.strptime(primeiro["leitura_anterior"], "%d/%m/%Y")
                ano_agosto = d.year if d.month >= 8 else d.year - 1
            except:
                ano_agosto = datetime.now().year - 1
        else:
            ano_agosto = datetime.now().year - 1
    elif mes_dias:
        anos = [k[0] for k in mes_dias]
        ano_agosto = min(anos)
    else:
        ano_agosto = datetime.now().year - 1

    # Monta a data real de cada mês (ago/ano_ago ... jul/ano_ago+1)
    def _data_mes(mes):
        ano = ano_agosto if mes >= 8 else ano_agosto + 1
        return datetime(ano, mes, 1)

    # --- Linha 1: nomes dos meses ---
    for mes in _MES_ORDEM:
        col_k = _MES_KWH_COL[mes]
        _set(ws1, 1, col_k, _NOMES_MES[mes], bold=True, align="center")

    # --- Linha 2: data (mmm-yy) + período ---
    # Períodos vêm das faturas; mapeia por mês
    periodo_por_mes = {}
    for fat in faturas:
        if fat.get("leitura_anterior"):
            try:
                d = datetime.strptime(fat["leitura_anterior"], "%d/%m/%Y")
                # o mês de referência da fatura é o mês seguinte à leitura anterior
                mes_ref = d.month + 1 if d.month < 12 else 1
                periodo_por_mes[mes_ref] = fat.get("periodo", "")
            except:
                pass

    for mes in _MES_ORDEM:
        col_d = _MES_DAT_COL[mes]
        col_k = _MES_KWH_COL[mes]
        dt = _data_mes(mes)
        c = ws1.cell(row=2, column=col_d, value=dt)
        c.number_format = "mmm-yy"
        _set(ws1, 2, col_k, periodo_por_mes.get(mes, ""), align="center")

    # --- Linhas 3..39: dados diários ---
    DATA_INI = 3
    DATA_FIM = 39
    max_dias = DATA_FIM - DATA_INI + 1  # 37

    for mes in _MES_ORDEM:
        col_d = _MES_DAT_COL[mes]
        col_k = _MES_KWH_COL[mes]
        dt_mes = _data_mes(mes)
        chave = (dt_mes.year, mes)
        dias = mes_dias.get(chave, [])
        for i, (data, kwh) in enumerate(dias[:max_dias]):
            row = DATA_INI + i
            c = ws1.cell(row=row, column=col_d, value=data)
            c.number_format = "mm-dd-yy"
            _set(ws1, row, col_k, round(kwh, 2), align="center")

    # --- Linha 40: label "Total" | Linha 41: fórmulas SUM ---
    _set(ws1, 41, 1, "Total", fmt="0.00")
    for mes in _MES_ORDEM:
        col_k = _MES_KWH_COL[mes]
        col_letter = get_column_letter(col_k)
        ws1.cell(row=41, column=col_k, value=f"=SUM({col_letter}3:{col_letter}39)").number_format = "0.00"

    # =========================================================
    # PLANILHA 2  —  resumo mensal (replica estrutura do template)
    # =========================================================
    ws2 = wb.create_sheet("Planilha2")

    # --- Linha 2: cabeçalhos ---
    cabecalhos = {
        "C2": "ENERGIA ATIVA",
        "D2": "ENERGIA INJETADA",
        "E2": "GERAÇÃO ",
        "F2": "CONSUMO LOCAL ",
        "G2": "CONSUMO TOTAL ",
        "J2": "GERAÇÃO PROPOSTA",
        "K2": "GERAÇÃO REAL ",
        "N2": "CONSUMO PROPOSTA",
        "O2": "CONSUMO REAL ",
        "R2": "CONSUMO PROPOSTA",
        "S2": "CONSUMO REAL ",
    }
    for addr, val in cabecalhos.items():
        c = ws2[addr]
        c.value = val
        c.font = Font(name="Calibri", size=11, bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center")

    # Mapeia faturas por mês para inserir na Planilha2
    fat_por_mes = {}
    for fat in faturas:
        if fat.get("leitura_anterior"):
            try:
                d = datetime.strptime(fat["leitura_anterior"], "%d/%m/%Y")
                mes_ref = d.month + 1 if d.month < 12 else 1
                fat_por_mes[mes_ref] = fat
            except:
                pass

    # Mapeamento de col kWh (Planilha1) → col_letter para referência cruzada
    p1_col_letters = {mes: get_column_letter(_MES_KWH_COL[mes]) for mes in _MES_ORDEM}

    # --- Linhas 3..14: dados mensais ---
    for i, mes in enumerate(_MES_ORDEM):
        row = 3 + i
        dt = _data_mes(mes)
        fat = fat_por_mes.get(mes, {})
        energia_ativa    = fat.get("energia_ativa_kwh")
        energia_injetada = fat.get("energia_injetada_kwh")
        p1_col = p1_col_letters[mes]

        # Col B: data (mmm-yy)
        c = ws2.cell(row=row, column=2, value=dt)
        c.number_format = "mmm-yy"

        # Col C: Energia Ativa (hardcoded da fatura)
        _set(ws2, row, 3, energia_ativa, align="center")

        # Col D: Energia Injetada (hardcoded da fatura)
        _set(ws2, row, 4, energia_injetada, align="center")

        # Col E: Geração = referência ao Total de Planilha 1
        ws2.cell(row=row, column=5, value=f"='Planilha 1'!{p1_col}41").number_format = "0"
        ws2.cell(row=row, column=5).alignment = Alignment(horizontal="center", vertical="center")

        # Col F: Consumo Local = E - D
        ws2.cell(row=row, column=6, value=f"=E{row}-D{row}").number_format = "0"
        ws2.cell(row=row, column=6).alignment = Alignment(horizontal="center", vertical="center")

        # Col G: Consumo Total = F + C
        ws2.cell(row=row, column=7, value=f"=F{row}+C{row}").number_format = "0"
        ws2.cell(row=row, column=7).alignment = Alignment(horizontal="center", vertical="center")

        # Col I: data (mmm-yy) — bloco Geração Proposta vs Real
        c2 = ws2.cell(row=row, column=9, value=dt)
        c2.number_format = "mmm-yy"

        # Col J: Geração Proposta (deixa em branco — usuário preenche)
        _set(ws2, row, 10, None, align="center")

        # Col K: Geração Real = E (cross-ref)
        ws2.cell(row=row, column=11, value=f"=E{row}").number_format = "0"
        ws2.cell(row=row, column=11).alignment = Alignment(horizontal="center", vertical="center")

        # Col M: data — bloco Consumo Proposta vs Real
        c3 = ws2.cell(row=row, column=13, value=dt)
        c3.number_format = "mmm-yy"

        # Col N: Consumo Proposta (deixa em branco)
        _set(ws2, row, 14, None, align="center")

        # Col O: Consumo Real = G
        ws2.cell(row=row, column=15, value=f"=G{row}").number_format = "0"
        ws2.cell(row=row, column=15).alignment = Alignment(horizontal="center", vertical="center")

        # Col Q: data — bloco extra Proposta vs Real
        c4 = ws2.cell(row=row, column=17, value=dt)
        c4.number_format = "mmm-yy"

        # Col R: Consumo Proposta (deixa em branco)
        _set(ws2, row, 18, None, align="center")

        # Col S: Consumo Real (deixa em branco — dado manual no template original)
        _set(ws2, row, 19, None, fmt="0", align="center")

    # --- Linha 15: Médias ---
    medias_b = [
        (2,  "Média"),
        (3,  "=AVERAGE(C3:C14)"),
        (4,  "=AVERAGE(D3:D14)"),
        (5,  "=AVERAGE(E3:E14)"),
        (6,  "=AVERAGE(F3:F14)"),
        (7,  "=AVERAGE(G3:G14)"),
        (9,  "Média "),
        (10, "=AVERAGE(J3:J14)"),
        (11, "=AVERAGE(K3:K14)"),
        (13, "Média "),
        (14, "=AVERAGE(N3:N14)"),
        (15, "=AVERAGE(O3:O14)"),
        (17, "Média "),
        (18, "=AVERAGE(R3:R14)"),
        (19, "=AVERAGE(S3:S14)"),
    ]
    for col, val in medias_b:
        c = ws2.cell(row=15, column=col, value=val)
        c.font = Font(name="Calibri", size=11, bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center")
        if isinstance(val, str) and val.startswith("="):
            c.number_format = "0"

    # --- Linha 16: PERFORMANCE ---
    pj = ws2.cell(row=16, column=10, value="PERFORMANCE")
    pj.font = Font(name="Calibri", size=11, bold=True)
    pj.fill = PatternFill("solid", start_color="FFFF00")

    pk = ws2.cell(row=16, column=11, value="=K15/J15")
    pk.number_format = "0%"
    pk.font = Font(name="Calibri", size=11, bold=True)
    pk.fill = PatternFill("solid", start_color="FFFF00")

    wb.save(out)
    print(f"  [xlsx] {out}")


# =============================================================================
# SALVA XLSX FINAL - formato do pipeline_energia_solar.py
# =============================================================================

def _hdr(ws, row, col, value, w=None):
    AZ = "1F4E79"
    c = ws.cell(row=row, column=col, value=value)
    c.font      = Font(bold=True, color="FFFFFF", name="Arial", size=11)
    c.fill      = PatternFill("solid", start_color=AZ)
    c.alignment = Alignment(horizontal="center", vertical="center")
    t = Side(style="thin", color="CCCCCC")
    c.border    = Border(left=t, right=t, top=t, bottom=t)
    if w:
        ws.column_dimensions[c.column_letter].width = w

def _cell(ws, row, col, value, fmt=None, bg=None):
    CZ = "F2F2F2"; BR = "FFFFFF"
    c = ws.cell(row=row, column=col, value=value)
    c.font      = Font(name="Arial", size=11)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.fill      = PatternFill("solid", start_color=bg or (CZ if row % 2 == 0 else BR))
    if fmt: c.number_format = fmt
    t = Side(style="thin", color="CCCCCC")
    c.border = Border(left=t, right=t, top=t, bottom=t)

def _adicionar_base_ia(wb, cliente: str, faturas: list, geracao_diaria: list):
    ws = wb.create_sheet("Base_IA")
    headers = [
        "cliente",
        "tipo",
        "data_inicio",
        "data_fim",
        "data",
        "mes_ref",
        "energia_ativa_kwh",
        "energia_injetada_kwh",
        "geracao_kwh",
        "periodo",
        "fonte_arquivo",
    ]

    for col, header in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=header)
        c.font = Font(bold=True, color="FFFFFF", name="Arial", size=11)
        c.fill = PatternFill("solid", start_color="305496")
        c.alignment = Alignment(horizontal="center", vertical="center")

    row_idx = 2
    for fat in faturas:
        inicio, atual = _datas_periodo_fatura(fat)
        fim = _fim_periodo_fatura(fat)
        mes_ref = _data_mes_ref(fat.get("mes"))
        if mes_ref:
            mes_ref_txt = _label_mes(mes_ref)
        elif inicio:
            mes_ref_txt = _label_mes(inicio)
        else:
            mes_ref_txt = fat.get("mes")

        valores = [
            cliente,
            "fatura",
            inicio,
            fim,
            None,
            mes_ref_txt,
            fat.get("energia_ativa_kwh"),
            fat.get("energia_injetada_kwh"),
            None,
            fat.get("periodo"),
            fat.get("fonte_arquivo"),
        ]
        for col, valor in enumerate(valores, 1):
            c = ws.cell(row=row_idx, column=col, value=valor)
            c.font = Font(name="Arial", size=10)
            if col in (3, 4, 5) and valor:
                c.number_format = "dd/mm/yyyy"
            if col in (7, 8, 9):
                c.number_format = "#,##0.00"
        row_idx += 1

    if geracao_diaria:
        df = pd.DataFrame(geracao_diaria)
        df["data"] = pd.to_datetime(df["data"])
        df = df.sort_values("data").reset_index(drop=True)
        for r in df.itertuples():
            data = r.data.to_pydatetime()
            valores = [
                cliente,
                "geracao",
                None,
                None,
                data,
                _label_mes(data),
                None,
                None,
                round(float(r.kwh), 4),
                None,
                getattr(r, "fonte_arquivo", None),
            ]
            for col, valor in enumerate(valores, 1):
                c = ws.cell(row=row_idx, column=col, value=valor)
                c.font = Font(name="Arial", size=10)
                if col == 5 and valor:
                    c.number_format = "dd/mm/yyyy"
                if col == 9:
                    c.number_format = "#,##0.0000"
            row_idx += 1

    widths = [18, 12, 14, 14, 14, 12, 18, 20, 16, 28, 42]
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
    ws.freeze_panes = "A2"

def salvar_xlsx(faturas: list, geracao_diaria: list, out: Path, cliente: str = ""):
    faturas = _normalizar_faturas_por_periodo(faturas)

    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Faturas"
    ws1.row_dimensions[1].height = 22

    hdrs = [
        ("Mes",               14),
        ("Periodo",           30),
        ("Leitura Anterior",  18),
        ("Leitura Atual",     18),
        ("Energia Ativa kWh", 20),
        ("Energia Injetada kWh", 22),
    ]
    for col, (h, w) in enumerate(hdrs, 1):
        _hdr(ws1, 1, col, h, w)

    for row, fat in enumerate(faturas, 2):
        _cell(ws1, row, 1, fat.get("mes"))
        _cell(ws1, row, 2, fat.get("periodo"))
        _cell(ws1, row, 3, fat.get("leitura_anterior"))
        _cell(ws1, row, 4, fat.get("leitura_atual"))
        _cell(ws1, row, 5, fat.get("energia_ativa_kwh"),    fmt="#,##0")
        _cell(ws1, row, 6, fat.get("energia_injetada_kwh"), fmt="#,##0")

    if faturas:
        tr = len(faturas) + 2
        ws1.cell(row=tr, column=4, value="TOTAL").font = Font(bold=True, name="Arial", size=11)
        ws1.cell(row=tr, column=5, value=f"=SUM(E2:E{tr-1})").number_format = "#,##0"
        ws1.cell(row=tr, column=6, value=f"=SUM(F2:F{tr-1})").number_format = "#,##0"
        for col in range(1, 7):
            ws1.cell(row=tr, column=col).font = Font(bold=True, name="Arial", size=11)
            ws1.cell(row=tr, column=col).fill = PatternFill("solid", start_color="BDD7EE")

    ws2 = wb.create_sheet("Geracao")
    ws2.row_dimensions[1].height = 22

    _hdr(ws2, 1, 1, "Data",          14)
    _hdr(ws2, 1, 2, "Geracao kWh",   16)
    _hdr(ws2, 1, 3, "Mes",           12)

    if geracao_diaria:
        df = pd.DataFrame(geracao_diaria)
        df["data"] = pd.to_datetime(df["data"])
        df = df.sort_values("data").reset_index(drop=True)

        for row, r in enumerate(df.itertuples(), 2):
            _cell(ws2, row, 1, r.data.strftime("%d/%m/%Y"))
            _cell(ws2, row, 2, round(r.kwh, 2), fmt="#,##0.00")
            _cell(ws2, row, 3, r.data.strftime("%b/%Y").upper())

        tr = len(df) + 2
        ws2.cell(row=tr, column=1, value="TOTAL").font = Font(bold=True, name="Arial", size=11)
        ws2.cell(row=tr, column=2, value=f"=SUM(B2:B{tr-1})").number_format = "#,##0.00"
        for col in range(1, 4):
            ws2.cell(row=tr, column=col).font = Font(bold=True, name="Arial", size=11)
            ws2.cell(row=tr, column=col).fill = PatternFill("solid", start_color="BDD7EE")

    _adicionar_base_ia(wb, cliente, faturas, geracao_diaria)
    wb.save(out)
    print(f"  [xlsx] {out}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  PIPELINE DE ENERGIA SOLAR v10")
    print("=" * 60)

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--cliente", default="")
    ap.add_argument("--listar-clientes", nargs="?", const="", default=None)
    ap.add_argument("--importar-baixados", action="store_true")
    ap.add_argument("--origem-downloads", default=str(DOWNLOADS_PADRAO))
    ap.add_argument("--dias-downloads", type=int, default=7)
    ap.add_argument("--sem-confirmar", action="store_true")
    ap.add_argument("--somente-importar", action="store_true")
    args, _ = ap.parse_known_args()

    if args.listar_clientes is not None:
        print("\nClientes encontrados:")
        for cliente in listar_clientes(args.listar_clientes):
            print(f"  - {cliente}")
        input("\nPressione Enter para fechar...")
        return

    nome_cliente = args.cliente.strip()
    if not nome_cliente:
        nome_cliente = input("\nNome do cliente: ").strip()
    if not nome_cliente:
        print("Nome do cliente nao informado.")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    try:
        pasta_cliente, pdf_dir, xlsx_dir, cliente_ja_existia = preparar_pasta_cliente(nome_cliente)
    except Exception as e:
        print(f"\nERRO: nao foi possivel preparar a pasta do cliente: {e}")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    print(f"\n  Cliente : {nome_cliente}")
    print(f"  Base    : {BASE_DIR}")
    print(f"  PDFs    : {pdf_dir}")
    print(f"  XLSXs   : {xlsx_dir}")
    if cliente_ja_existia:
        print("  Pasta   : cliente existente")
    else:
        print("  Pasta   : cliente criado agora")

    if args.importar_baixados:
        origem_downloads = Path(args.origem_downloads).expanduser()
        print("\n[0/3] Importando arquivos baixados...")
        print(f"  Origem : {origem_downloads}")
        print(f"  Janela : ultimos {args.dias_downloads} dias")
        qtd_pdfs, qtd_planilhas, qtd_quarentena, importacao_confirmada = importar_baixados(
            pasta_cliente,
            origem_downloads,
            args.dias_downloads,
            confirmar=not args.sem_confirmar,
        )
        if not importacao_confirmada:
            input("\nPressione Enter para fechar...")
            return
        print(f"  PDFs copiados  : {qtd_pdfs}")
        print(f"  XLSXs copiados : {qtd_planilhas}")
        print(f"  Originais movidos para quarentena: {qtd_quarentena}")
        if args.somente_importar:
            input("\nPressione Enter para fechar...")
            return

    pdf_paths, origem_pdfs = coletar_com_fallback(pasta_cliente, pdf_dir, (".pdf",))
    xlsx_paths, origem_xlsx = coletar_com_fallback(pasta_cliente, xlsx_dir, (".xlsx", ".xls"))

    print(f"\n  PDFs encontrados  : {len(pdf_paths)}")
    print(f"  XLSXs encontrados : {len(xlsx_paths)}")
    print(f"  Origem PDFs       : {origem_pdfs}")
    print(f"  Origem XLSXs      : {origem_xlsx}")

    if not pdf_paths and not xlsx_paths:
        print("\nNenhum arquivo encontrado nas pastas.")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    print("\n[1/3] Extraindo faturas PDF...")
    faturas = extrair_faturas(pdf_paths) if pdf_paths else []

    print("\n[2/3] Consolidando relatorios de geracao...")
    if xlsx_paths:
        geracao_diaria, detalhes_geracao = extrair_geracao(xlsx_paths, retornar_detalhes=True)
    else:
        geracao_diaria, detalhes_geracao = [], []

    diagnosticar_conjunto(pdf_paths, xlsx_paths, faturas, detalhes_geracao)

    print("\n[3/3] Salvando XLSX...")
    pasta_out = Path.home() / "Desktop" / "Analise Energia"
    pasta_out.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = pasta_out / f"Dados IA - {nome_cliente} - {ts}.xlsx"
    salvar_xlsx(faturas, geracao_diaria, out, nome_cliente)

    total_kwh      = sum(r["kwh"] for r in geracao_diaria)
    total_ativo    = sum(f["energia_ativa_kwh"]    for f in faturas if f.get("energia_ativa_kwh"))
    total_injetado = sum(f["energia_injetada_kwh"] for f in faturas if f.get("energia_injetada_kwh"))

    print("\n" + "=" * 60)
    print(f"  Arquivo : {out}")
    print(f"  Faturas : {len(faturas)} meses")
    print(f"  Geracao : {len(geracao_diaria)} dias | {round(total_kwh, 1)} kWh total")
    print(f"  Ativo   : {total_ativo} kWh | Injetado: {total_injetado} kWh")
    print("=" * 60)
    print("\nAnexe o arquivo no chat e pergunte o que quiser.")
    input("\nPressione Enter para fechar...")


if __name__ == "__main__":
    main()
