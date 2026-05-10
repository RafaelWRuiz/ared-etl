from __future__ import annotations

from pathlib import Path
import sys
import unicodedata

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from ared.normalizar import normalizar_texto  # noqa: E402


ARQ_STAGING = RAIZ_PROJETO / "saida/staging/stg_alunos_normalizado.xlsx"
DIR_SAIDA = RAIZ_PROJETO / "saida/curated"
ARQ_FATO = DIR_SAIDA / "fato_alunos_turma_semestre.xlsx"
ARQ_RELATORIO = DIR_SAIDA / "RELATORIO_CURATED_ALUNOS.xlsx"


def normalizar_nome_coluna(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", normalizar_texto(nome))
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return texto.upper()


def resolver_coluna(df: pd.DataFrame, nome_esperado: str) -> str:
    mapa = {normalizar_nome_coluna(coluna): coluna for coluna in df.columns}
    chave = normalizar_nome_coluna(nome_esperado)
    if chave not in mapa:
        raise KeyError(f"Coluna obrigatória não encontrada: {nome_esperado}")
    return mapa[chave]


def carregar_staging() -> pd.DataFrame:
    return pd.read_excel(ARQ_STAGING)


def gerar_chave_turma_semestre(df: pd.DataFrame) -> pd.Series:
    partes = [
        df["ano_referencia"].astype(str),
        df["semestre_referencia"].astype(str),
        df["codigo_unidade_canonico"].map(normalizar_texto),
        df["numero_turma"].map(normalizar_texto),
        df["turma_raw"].map(normalizar_texto),
    ]
    chave = partes[0]
    for parte in partes[1:]:
        chave = chave + "|" + parte
    return chave


def montar_curated(df_staging: pd.DataFrame) -> pd.DataFrame:
    colunas_base = {
        "ano_referencia": resolver_coluna(df_staging, "ano_referencia"),
        "semestre_referencia": resolver_coluna(df_staging, "semestre_referencia"),
        "codigo_unidade_canonico": resolver_coluna(df_staging, "codigo_unidade_canonico"),
        "nome_unidade_canonico": resolver_coluna(df_staging, "nome_unidade_canonico"),
        "curso_canonico": resolver_coluna(df_staging, "curso_canonico"),
        "tipo_etapa": resolver_coluna(df_staging, "tipo_etapa"),
        "ordem_etapa": resolver_coluna(df_staging, "ordem_etapa"),
        "flag_entrada": resolver_coluna(df_staging, "flag_entrada"),
        "periodo_canonico": resolver_coluna(df_staging, "periodo_canonico"),
        "cod_periodo_ared": resolver_coluna(df_staging, "cod_periodo_ared"),
        "tipo_local_oferta": resolver_coluna(df_staging, "tipo_local_oferta"),
        "tipo_ensino": resolver_coluna(df_staging, "Tipo de Ensino"),
        "turma_raw": resolver_coluna(df_staging, "Turma"),
        "numero_turma": resolver_coluna(df_staging, "Número da Turma"),
    }

    colunas_metricas = {
        "total_alunos": resolver_coluna(df_staging, "Total de Alunos"),
        "sexo_feminino": resolver_coluna(df_staging, "Sexo Feminino"),
        "sexo_masculino": resolver_coluna(df_staging, "Sexo Masculino"),
        "medio_na_etec": resolver_coluna(df_staging, "Médio na ETEC"),
        "medio_em_outra_etec": resolver_coluna(df_staging, "Médio em outra ETEC"),
        "medio_fora_do_cps": resolver_coluna(df_staging, "Médio fora do CPS"),
        "medio_concluido": resolver_coluna(df_staging, "Médio Concluído"),
        "aprovados": resolver_coluna(df_staging, "Aprovados"),
        "promocao_parcial": resolver_coluna(df_staging, "Promoção Parcial"),
        "retidos_por_frequencia": resolver_coluna(df_staging, "Retidos por Frequência"),
        "retidos_por_rendimento": resolver_coluna(df_staging, "Retidos por Rendimento"),
        "retidos_por_freq_e_rendimento": resolver_coluna(
            df_staging, "Retidos por Frequencia e Rendimento"
        ),
        "retencao_parcial": resolver_coluna(df_staging, "Retenção Parcial"),
        "desistencias": resolver_coluna(df_staging, "Desistências"),
        "transferencias_expedidas": resolver_coluna(df_staging, "Transferências Expedidas"),
        "transferencias_recebidas": resolver_coluna(df_staging, "Transferências Recebidas"),
        "trancamentos": resolver_coluna(df_staging, "Trancamentos"),
    }

    selecionadas = {**colunas_base, **colunas_metricas}
    curated = df_staging[[selecionadas[coluna] for coluna in selecionadas]].copy()
    curated.columns = list(selecionadas.keys())

    colunas_numericas = [
        "ano_referencia",
        "semestre_referencia",
        "ordem_etapa",
        "total_alunos",
        "sexo_feminino",
        "sexo_masculino",
        "medio_na_etec",
        "medio_em_outra_etec",
        "medio_fora_do_cps",
        "medio_concluido",
        "aprovados",
        "promocao_parcial",
        "retidos_por_frequencia",
        "retidos_por_rendimento",
        "retidos_por_freq_e_rendimento",
        "retencao_parcial",
        "desistencias",
        "transferencias_expedidas",
        "transferencias_recebidas",
        "trancamentos",
    ]
    for coluna in colunas_numericas:
        curated[coluna] = pd.to_numeric(curated[coluna], errors="coerce")

    curated["retidos"] = (
        curated["retidos_por_frequencia"].fillna(0)
        + curated["retidos_por_rendimento"].fillna(0)
        + curated["retidos_por_freq_e_rendimento"].fillna(0)
    )
    curated["transferencias"] = (
        curated["transferencias_expedidas"].fillna(0) + curated["transferencias_recebidas"].fillna(0)
    )
    curated["chave_turma_semestre"] = gerar_chave_turma_semestre(curated)

    ordem_final = [
        "chave_turma_semestre",
        "ano_referencia",
        "semestre_referencia",
        "codigo_unidade_canonico",
        "nome_unidade_canonico",
        "curso_canonico",
        "tipo_etapa",
        "ordem_etapa",
        "flag_entrada",
        "periodo_canonico",
        "cod_periodo_ared",
        "tipo_local_oferta",
        "tipo_ensino",
        "turma_raw",
        "numero_turma",
        "total_alunos",
        "sexo_feminino",
        "sexo_masculino",
        "medio_na_etec",
        "medio_em_outra_etec",
        "medio_fora_do_cps",
        "medio_concluido",
        "aprovados",
        "promocao_parcial",
        "retidos",
        "retidos_por_frequencia",
        "retidos_por_rendimento",
        "retidos_por_freq_e_rendimento",
        "retencao_parcial",
        "desistencias",
        "transferencias",
        "transferencias_expedidas",
        "transferencias_recebidas",
        "trancamentos",
    ]
    return curated[ordem_final]


def montar_relatorio(df_curated: pd.DataFrame) -> dict[str, pd.DataFrame]:
    resumo = pd.DataFrame(
        [
            {
                "linhas": len(df_curated),
                "colunas": len(df_curated.columns),
                "chaves_unicas": df_curated["chave_turma_semestre"].nunique(),
            }
        ]
    )

    colunas_finais = pd.DataFrame({"coluna": list(df_curated.columns)})

    duplicidades = df_curated[df_curated["chave_turma_semestre"].duplicated(keep=False)].copy()
    cardinalidade = pd.DataFrame(
        [
            {
                "linhas": len(df_curated),
                "chaves_unicas": df_curated["chave_turma_semestre"].nunique(),
                "duplicidades": len(duplicidades),
            }
        ]
    )

    contagem_tipo_etapa = (
        df_curated["tipo_etapa"]
        .value_counts(dropna=False)
        .rename_axis("tipo_etapa")
        .reset_index(name="quantidade")
    )

    contagem_tipo_ensino = (
        df_curated["tipo_ensino"]
        .value_counts(dropna=False)
        .rename_axis("tipo_ensino")
        .reset_index(name="quantidade")
    )

    top_cursos = (
        df_curated["curso_canonico"]
        .value_counts(dropna=False)
        .head(20)
        .rename_axis("curso_canonico")
        .reset_index(name="quantidade")
    )

    top_unidades = (
        df_curated["nome_unidade_canonico"]
        .value_counts(dropna=False)
        .head(20)
        .rename_axis("nome_unidade_canonico")
        .reset_index(name="quantidade")
    )

    return {
        "resumo": resumo,
        "colunas_finais": colunas_finais,
        "cardinalidade_chave": cardinalidade,
        "duplicidades": duplicidades,
        "contagem_tipo_etapa": contagem_tipo_etapa,
        "contagem_tipo_ensino": contagem_tipo_ensino,
        "top_cursos": top_cursos,
        "top_unidades": top_unidades,
    }


def exportar(df_curated: pd.DataFrame, relatorio: dict[str, pd.DataFrame]) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    df_curated.to_excel(ARQ_FATO, index=False)

    with pd.ExcelWriter(ARQ_RELATORIO, engine="openpyxl") as writer:
        for nome_aba, tabela in relatorio.items():
            tabela.to_excel(writer, sheet_name=nome_aba, index=False)


def main() -> None:
    df_staging = carregar_staging()
    df_curated = montar_curated(df_staging)
    relatorio = montar_relatorio(df_curated)
    exportar(df_curated, relatorio)

    duplicidades = len(relatorio["duplicidades"])
    print(f"Arquivo gerado: {ARQ_FATO}")
    print(f"Arquivo gerado: {ARQ_RELATORIO}")
    print(f"Linhas curated: {len(df_curated)}")
    print(f"Chaves únicas: {df_curated['chave_turma_semestre'].nunique()}")
    print(f"Duplicidades: {duplicidades}")


if __name__ == "__main__":
    main()
