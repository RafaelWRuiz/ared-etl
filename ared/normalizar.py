from __future__ import annotations

from typing import Any, TypedDict
import unicodedata
import re

import pandas as pd


class CursoNormalizado(TypedDict):
    curso_canonico: str
    flag_mtec: bool
    flag_mtec_pi: bool
    flag_ams: bool
    flag_mnp: bool
    flag_ead: bool
    flag_nao_mapeado: bool


class UnidadeNormalizada(TypedDict):
    codigo_unidade_canonico: str
    nome_unidade_canonico: str
    tipo_local_oferta: str
    flag_nao_mapeado: bool


class PeriodoNormalizado(TypedDict):
    periodo_canonico: str
    cod_periodo_ared: str
    flag_nao_mapeado: bool


class EtapaNormalizada(TypedDict):
    tipo_etapa: str
    ordem_etapa: int | None
    flag_entrada: bool | None
    flag_nao_mapeado: bool


def normalizar_texto(valor: Any) -> str:
    """
    Normaliza texto para uso consistente no ETL.

    Regras:
    - converte valores nulos em string vazia
    - aplica normalização Unicode
    - remove espaços duplicados
    - aplica trim
    """
    if pd.isna(valor):
        return ""

    texto = unicodedata.normalize("NFKC", str(valor))
    return " ".join(texto.split()).strip()


def _normalizar_chave(valor: Any) -> str:
    texto = normalizar_texto(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    texto = (
        texto.replace("ª", "A")
        .replace("º", "O")
        .replace("°", "O")
        .replace("˚", "O")
    )
    texto = re.sub(r"(\d)\?\s+M", r"\1O M", texto)
    texto = re.sub(r"(\d)\?\s+S", r"\1A S", texto)
    texto = re.sub(r"M\?DULO", "MODULO", texto, flags=re.IGNORECASE)
    texto = re.sub(r"S\?RIE", "SERIE", texto, flags=re.IGNORECASE)
    return texto.upper()


def _coluna_por_nome_normalizado(df: pd.DataFrame, nome_esperado: str) -> str:
    mapa_colunas = {_normalizar_chave(coluna): coluna for coluna in df.columns}
    chave = _normalizar_chave(nome_esperado)

    if chave not in mapa_colunas:
        raise KeyError(f"Coluna obrigatória não encontrada: {nome_esperado}")

    return mapa_colunas[chave]


def _para_bool(valor: Any) -> bool:
    return _normalizar_chave(valor) in {"SIM", "TRUE", "1"}


def normalizar_curso(curso_raw: Any, ref_cursos_df: pd.DataFrame) -> CursoNormalizado:
    """
    Normaliza um curso bruto usando a tabela de referência de cursos.

    Se não encontrar o curso, retorna o valor original normalizado e marca
    `flag_nao_mapeado=True`.
    """
    curso_limpo = normalizar_texto(curso_raw)

    col_curso_raw = _coluna_por_nome_normalizado(ref_cursos_df, "curso_raw")
    col_curso_canonico = _coluna_por_nome_normalizado(ref_cursos_df, "curso_canonico")
    col_flag_mtec = _coluna_por_nome_normalizado(ref_cursos_df, "flag_mtec")
    col_flag_mtec_pi = _coluna_por_nome_normalizado(ref_cursos_df, "flag_mtec_pi")
    col_flag_ams = _coluna_por_nome_normalizado(ref_cursos_df, "flag_ams")
    col_flag_mnp = _coluna_por_nome_normalizado(ref_cursos_df, "flag_mnp")
    col_flag_ead = _coluna_por_nome_normalizado(ref_cursos_df, "flag_ead")

    correspondencias = ref_cursos_df[
        ref_cursos_df[col_curso_raw].map(_normalizar_chave) == _normalizar_chave(curso_limpo)
    ]

    if correspondencias.empty:
        return {
            "curso_canonico": curso_limpo,
            "flag_mtec": False,
            "flag_mtec_pi": False,
            "flag_ams": False,
            "flag_mnp": False,
            "flag_ead": False,
            "flag_nao_mapeado": True,
        }

    linha = correspondencias.iloc[0]
    return {
        "curso_canonico": normalizar_texto(linha[col_curso_canonico]),
        "flag_mtec": _para_bool(linha[col_flag_mtec]),
        "flag_mtec_pi": _para_bool(linha[col_flag_mtec_pi]),
        "flag_ams": _para_bool(linha[col_flag_ams]),
        "flag_mnp": _para_bool(linha[col_flag_mnp]),
        "flag_ead": _para_bool(linha[col_flag_ead]),
        "flag_nao_mapeado": False,
    }


def normalizar_unidade(
    codigo_raw: Any,
    nome_raw: Any,
    ref_unidades_df: pd.DataFrame,
) -> UnidadeNormalizada:
    """
    Normaliza uma unidade/local de oferta usando a tabela de referência.

    O lookup é feito pela combinação de código e nome originais.
    """
    codigo_limpo = normalizar_texto(codigo_raw)
    nome_limpo = normalizar_texto(nome_raw)

    col_codigo_raw = _coluna_por_nome_normalizado(ref_unidades_df, "codigo_unidade_raw")
    col_nome_raw = _coluna_por_nome_normalizado(ref_unidades_df, "nome_unidade_raw")
    col_codigo_canonico = _coluna_por_nome_normalizado(ref_unidades_df, "codigo_unidade_canonico")
    col_nome_canonico = _coluna_por_nome_normalizado(ref_unidades_df, "nome_unidade_canonico")
    col_tipo_local = _coluna_por_nome_normalizado(ref_unidades_df, "tipo_local_oferta")

    correspondencias = ref_unidades_df[
        (ref_unidades_df[col_codigo_raw].map(_normalizar_chave) == _normalizar_chave(codigo_limpo))
        & (ref_unidades_df[col_nome_raw].map(_normalizar_chave) == _normalizar_chave(nome_limpo))
    ]

    if correspondencias.empty:
        return {
            "codigo_unidade_canonico": codigo_limpo,
            "nome_unidade_canonico": nome_limpo,
            "tipo_local_oferta": "NAO_MAPEADO",
            "flag_nao_mapeado": True,
        }

    linha = correspondencias.iloc[0]
    return {
        "codigo_unidade_canonico": normalizar_texto(linha[col_codigo_canonico]),
        "nome_unidade_canonico": normalizar_texto(linha[col_nome_canonico]),
        "tipo_local_oferta": normalizar_texto(linha[col_tipo_local]),
        "flag_nao_mapeado": False,
    }


def normalizar_periodo(periodo_raw: Any, ref_periodo_df: pd.DataFrame) -> PeriodoNormalizado:
    """
    Normaliza um período usando a tabela de referência de períodos.
    """
    periodo_limpo = normalizar_texto(periodo_raw)

    col_periodo_raw = _coluna_por_nome_normalizado(ref_periodo_df, "periodo_raw")
    col_periodo_canonico = _coluna_por_nome_normalizado(ref_periodo_df, "periodo_canonico")
    col_cod_ared = _coluna_por_nome_normalizado(ref_periodo_df, "cod_periodo_ared")

    correspondencias = ref_periodo_df[
        ref_periodo_df[col_periodo_raw].map(_normalizar_chave) == _normalizar_chave(periodo_limpo)
    ]

    if correspondencias.empty:
        return {
            "periodo_canonico": periodo_limpo,
            "cod_periodo_ared": "REVISAR",
            "flag_nao_mapeado": True,
        }

    linha = correspondencias.iloc[0]
    return {
        "periodo_canonico": normalizar_texto(linha[col_periodo_canonico]),
        "cod_periodo_ared": normalizar_texto(linha[col_cod_ared]) or "REVISAR",
        "flag_nao_mapeado": False,
    }


def normalizar_etapa(turma_raw: Any, ref_etapa_df: pd.DataFrame) -> EtapaNormalizada:
    """
    Normaliza a etapa da turma usando a tabela de referência de etapas.
    """
    turma_limpa = normalizar_texto(turma_raw)

    col_turma_raw = _coluna_por_nome_normalizado(ref_etapa_df, "turma_raw")
    col_tipo_etapa = _coluna_por_nome_normalizado(ref_etapa_df, "tipo_etapa")
    col_ordem_etapa = _coluna_por_nome_normalizado(ref_etapa_df, "ordem_etapa")
    col_flag_entrada = _coluna_por_nome_normalizado(ref_etapa_df, "flag_entrada")

    correspondencias = ref_etapa_df[
        ref_etapa_df[col_turma_raw].map(_normalizar_chave) == _normalizar_chave(turma_limpa)
    ]

    if correspondencias.empty:
        return {
            "tipo_etapa": "NAO_MAPEADO",
            "ordem_etapa": None,
            "flag_entrada": None,
            "flag_nao_mapeado": True,
        }

    linha = correspondencias.iloc[0]
    ordem_valor = linha[col_ordem_etapa]
    ordem = int(ordem_valor) if not pd.isna(ordem_valor) else None

    return {
        "tipo_etapa": normalizar_texto(linha[col_tipo_etapa]),
        "ordem_etapa": ordem,
        "flag_entrada": _para_bool(linha[col_flag_entrada]),
        "flag_nao_mapeado": False,
    }


if __name__ == "__main__":
    caminho_base = "dados_brutos/referencias"
    ref_cursos = pd.read_excel(f"{caminho_base}/ref_mapeamento_curso.xlsx")
    ref_unidades = pd.read_excel(f"{caminho_base}/ref_mapeamento_unidade.xlsx")
    ref_periodo = pd.read_excel(f"{caminho_base}/ref_periodo.xlsx")
    ref_etapa = pd.read_excel(f"{caminho_base}/ref_etapa_turma.xlsx")

    print("Exemplo curso:")
    print(normalizar_curso("Administração - MTec-PI", ref_cursos))
    print("\nExemplo unidade:")
    print(
        normalizar_unidade(
            "010.02 - Ext/Etec",
            "Etec Lauro Gomes (EE Prof.ª Cynira Pires dos Santos)",
            ref_unidades,
        )
    )
    print("\nExemplo período:")
    print(normalizar_periodo("Manhã e Tarde", ref_periodo))
    print("\nExemplo etapa:")
    print(normalizar_etapa("1ª Série", ref_etapa))
