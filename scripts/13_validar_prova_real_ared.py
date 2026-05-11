from __future__ import annotations

from pathlib import Path
import sys
import unicodedata

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from ared.normalizar import (  # noqa: E402
    normalizar_curso,
    normalizar_periodo,
    normalizar_texto,
    normalizar_unidade,
)


ARQ_PIPELINE = RAIZ_PROJETO / "saida/ARED_OPERACIONAL.xlsx"
ARQ_GABARITO = RAIZ_PROJETO / "GABARITO_ARED_2026_2.xlsx"
ARQ_REF_CURSOS = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_curso.xlsx"
ARQ_REF_UNIDADES = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_unidade.xlsx"
ARQ_REF_PERIODO = RAIZ_PROJETO / "dados_brutos/referencias/ref_periodo.xlsx"
ARQ_SAIDA = RAIZ_PROJETO / "saida/VALIDACAO_PROVA_REAL.xlsx"

ABA_GABARITO = "ARED 2026.2"
ABA_GABARITO_BASE = "Base Agregada"
TOLERANCIA = 0.02
CHAVES_MATCH = [
    "unidade_canonica",
    "curso_canonico",
    "periodo",
    "tipo_ensino",
    "ano",
    "semestre",
]


def normalizar_nome_coluna(nome: object) -> str:
    texto = normalizar_texto(nome)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return texto.upper()


def montar_cabecalho_principal(df_bruto: pd.DataFrame) -> list[object]:
    cabecalho = df_bruto.iloc[4].tolist()
    return [normalizar_texto(valor) for valor in cabecalho]


def carregar_referencias() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_excel(ARQ_REF_CURSOS, sheet_name="ref_mapeamento_curso"),
        pd.read_excel(ARQ_REF_UNIDADES, sheet_name="ref_mapeamento_unidade"),
        pd.read_excel(ARQ_REF_PERIODO, sheet_name="ref_periodo"),
    )


def resolver_coluna(df: pd.DataFrame, nome_esperado: str) -> str:
    mapa = {normalizar_nome_coluna(coluna): coluna for coluna in df.columns}
    chave = normalizar_nome_coluna(nome_esperado)
    if chave not in mapa:
        raise KeyError(f"Coluna obrigatoria nao encontrada: {nome_esperado}")
    return mapa[chave]


def carregar_pipeline() -> pd.DataFrame:
    df = pd.read_excel(ARQ_PIPELINE)
    mask = (
        df["flag_coorte_completa"].map(normalizar_texto).str.upper().eq("SIM")
        & df["acumulado_percentual"].notna()
    )
    base = df.loc[mask].copy()

    base["ano"] = pd.to_numeric(base["ano"], errors="coerce").astype("Int64")
    base["semestre"] = pd.to_numeric(base["semestre"], errors="coerce").astype("Int64")

    for coluna in ["op2_percentual", "op3_percentual", "op4_percentual", "acumulado_percentual"]:
        base[coluna] = pd.to_numeric(base[coluna], errors="coerce")

    base["nivel_ared"] = base["nivel_ared"].map(normalizar_texto)
    base["diagnostico_ared"] = base["diagnostico_ared"].map(normalizar_texto)

    base = base.sort_values(
        [
            "ano",
            "semestre",
            "unidade_canonica",
            "curso_canonico",
            "periodo",
            "tipo_ensino",
            "ordem_etapa",
        ],
        na_position="last",
    ).reset_index(drop=True)

    base["pipeline_match_key"] = base[CHAVES_MATCH].astype(str).agg("|".join, axis=1)
    return base


def carregar_gabarito(
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
) -> pd.DataFrame:
    principal_bruto = pd.read_excel(ARQ_GABARITO, sheet_name=ABA_GABARITO, header=None)
    cabecalho = montar_cabecalho_principal(principal_bruto)
    principal = principal_bruto.iloc[5:].copy()
    principal.columns = cabecalho
    principal = principal.dropna(how="all").reset_index(drop=True)

    base_agregada = pd.read_excel(ARQ_GABARITO, sheet_name=ABA_GABARITO_BASE)
    base_agregada = base_agregada.rename(columns={" Turma": "Turma_base"})
    meta = (
        base_agregada[
            ["Código Localizador", "Ano", "Tipo de Ensino", "Unidades do CEETEPS", "Habilitação/Curso", "Período"]
        ]
        .dropna(subset=["Código Localizador"])
        .drop_duplicates(subset=["Código Localizador"])
        .copy()
    )

    df = principal.merge(meta, on="Código Localizador", how="left", suffixes=("", "_base"))

    df["ano_semestre_gabarito"] = df["Ano"].map(normalizar_texto)
    df["ano"] = pd.to_numeric(df["ano_semestre_gabarito"].str.split(".").str[0], errors="coerce").astype("Int64")
    df["semestre"] = pd.to_numeric(df["ano_semestre_gabarito"].str.split(".").str[1], errors="coerce").astype("Int64")

    unidades = df.apply(
        lambda linha: normalizar_unidade(
            codigo_raw=linha["Códigos Unidades"],
            nome_raw=linha["Unidades do CEETEPS"],
            ref_unidades_df=ref_unidades,
        ),
        axis=1,
    )
    cursos = df["Habilitação/Curso"].map(lambda valor: normalizar_curso(valor, ref_cursos))
    periodos = df["Período"].map(lambda valor: normalizar_periodo(valor, ref_periodo))

    df["unidade_canonica"] = unidades.map(lambda valor: valor["nome_unidade_canonico"])
    df["curso_canonico"] = cursos.map(lambda valor: valor["curso_canonico"])
    df["periodo"] = periodos.map(lambda valor: valor["periodo_canonico"])
    df["tipo_ensino"] = df["Tipo de Ensino"].map(normalizar_texto)

    mapa_renomear = {
        "OP 2": "gabarito_op2_percentual",
        "OP 3": "gabarito_op3_percentual",
        "OP 4": "gabarito_op4_percentual",
        "Acumulado": "gabarito_acumulado_percentual",
        "Nível": "gabarito_nivel_ared",
        "Diagnóstico": "gabarito_diagnostico_ared",
    }
    df = df.rename(columns=mapa_renomear)

    for coluna in [
        "gabarito_op2_percentual",
        "gabarito_op3_percentual",
        "gabarito_op4_percentual",
        "gabarito_acumulado_percentual",
    ]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    df["gabarito_nivel_ared"] = df["gabarito_nivel_ared"].map(normalizar_texto)
    df["gabarito_diagnostico_ared"] = df["gabarito_diagnostico_ared"].map(normalizar_texto)
    df["gabarito_match_key"] = df[CHAVES_MATCH].astype(str).agg("|".join, axis=1)
    return df


def comparar_numerico(serie_pipeline: pd.Series, serie_gabarito: pd.Series) -> tuple[pd.Series, pd.Series]:
    diferenca = serie_pipeline - serie_gabarito
    aderente = diferenca.abs().le(TOLERANCIA) & serie_pipeline.notna() & serie_gabarito.notna()
    return diferenca, aderente


def comparar_texto(serie_pipeline: pd.Series, serie_gabarito: pd.Series) -> pd.Series:
    return (
        serie_pipeline.map(normalizar_texto).eq(serie_gabarito.map(normalizar_texto))
        & serie_pipeline.notna()
        & serie_gabarito.notna()
    )


def montar_matches(df_pipeline: pd.DataFrame, df_gabarito: pd.DataFrame) -> pd.DataFrame:
    col_mod1 = resolver_coluna(df_gabarito, "1º Módulo")
    col_mod2 = resolver_coluna(df_gabarito, "2º Módulo")
    col_mod3 = resolver_coluna(df_gabarito, "3º Módulo")
    col_mod4 = resolver_coluna(df_gabarito, "4º Módulo")

    cols_pipeline = [
        *CHAVES_MATCH,
        "arquivo_origem",
        "unidade_original",
        "curso_original",
        "tipo_oferta",
        "etapa",
        "tipo_etapa",
        "ordem_etapa",
        "total_alunos",
        "duracao_etapas",
        "duracao_coorte",
        "ano_entrada",
        "semestre_entrada",
        "vagas_entrada",
        "inscritos_entrada",
        "demanda_entrada",
        "flag_match_vestibulinho",
        "op2_total_alunos",
        "op3_total_alunos",
        "op4_total_alunos",
        "op2_percentual",
        "op3_percentual",
        "op4_percentual",
        "acumulado_percentual",
        "nivel_ared",
        "diagnostico_ared",
        "pipeline_match_key",
    ]
    cols_gabarito = [
        "Código Localizador",
        "Códigos Sede",
        "Códigos Unidades",
        "Unidades do CEETEPS",
        "Habilitação/Curso",
        "Período",
        "Tipo de Ensino",
        "Inscritos",
        "Vagas",
        "Turmas",
        "Demanda",
        col_mod1,
        "OP 1",
        col_mod2,
        "gabarito_op2_percentual",
        col_mod3,
        "gabarito_op3_percentual",
        col_mod4,
        "gabarito_op4_percentual",
        "gabarito_acumulado_percentual",
        "gabarito_nivel_ared",
        "gabarito_diagnostico_ared",
        "ano_semestre_gabarito",
        "gabarito_match_key",
    ]

    matches = df_pipeline[cols_pipeline].merge(
        df_gabarito[cols_gabarito + CHAVES_MATCH],
        on=CHAVES_MATCH,
        how="inner",
        suffixes=("_pipeline", "_gabarito"),
    )

    matches["diferenca_op2"], matches["flag_match_op2"] = comparar_numerico(
        matches["op2_percentual"],
        matches["gabarito_op2_percentual"],
    )
    matches["diferenca_op3"], matches["flag_match_op3"] = comparar_numerico(
        matches["op3_percentual"],
        matches["gabarito_op3_percentual"],
    )
    matches["diferenca_op4"], matches["flag_match_op4"] = comparar_numerico(
        matches["op4_percentual"],
        matches["gabarito_op4_percentual"],
    )
    matches["diferenca_acumulado"], matches["flag_match_acumulado"] = comparar_numerico(
        matches["acumulado_percentual"],
        matches["gabarito_acumulado_percentual"],
    )
    matches["flag_match_nivel"] = comparar_texto(matches["nivel_ared"], matches["gabarito_nivel_ared"])
    matches["flag_match_diagnostico"] = comparar_texto(
        matches["diagnostico_ared"],
        matches["gabarito_diagnostico_ared"],
    )
    matches["flag_match_perfeito"] = (
        matches["flag_match_op2"]
        & matches["flag_match_op3"]
        & matches["flag_match_op4"]
        & matches["flag_match_acumulado"]
        & matches["flag_match_nivel"]
        & matches["flag_match_diagnostico"]
    )
    return matches


def montar_sem_match_pipeline(df_pipeline: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    usados = set(matches["pipeline_match_key"])
    return df_pipeline.loc[~df_pipeline["pipeline_match_key"].isin(usados)].copy()


def montar_sem_match_gabarito(df_gabarito: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    usados = set(matches["gabarito_match_key"])
    return df_gabarito.loc[~df_gabarito["gabarito_match_key"].isin(usados)].copy()


def montar_divergencias(matches: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return matches.copy()

    flags = [
        "flag_match_op2",
        "flag_match_op3",
        "flag_match_op4",
        "flag_match_acumulado",
        "flag_match_nivel",
        "flag_match_diagnostico",
    ]
    divergencias = matches.loc[~matches[flags].all(axis=1)].copy()
    return divergencias.sort_values(
        ["diferenca_acumulado", "diferenca_op4", "diferenca_op3", "diferenca_op2"],
        key=lambda serie: serie.abs() if pd.api.types.is_numeric_dtype(serie) else serie,
        ascending=False,
        na_position="last",
    )


def percentual_flags(matches: pd.DataFrame, coluna: str) -> float:
    if matches.empty:
        return 0.0
    return float(matches[coluna].mean())


def montar_resumo(
    df_pipeline: pd.DataFrame,
    df_gabarito: pd.DataFrame,
    matches: pd.DataFrame,
    divergencias: pd.DataFrame,
    sem_match_pipeline: pd.DataFrame,
    sem_match_gabarito: pd.DataFrame,
) -> pd.DataFrame:
    if matches.empty:
        top_match_1 = "Sem matches comparaveis"
        top_match_2 = "Sem matches comparaveis"
        top_match_3 = "Sem matches comparaveis"
    else:
        perfeitos = matches.loc[matches["flag_match_perfeito"]].head(3)
        descricoes = (
            perfeitos["unidade_canonica"]
            + " | "
            + perfeitos["curso_canonico"]
            + " | "
            + perfeitos["periodo"]
            + " | "
            + perfeitos["tipo_ensino"]
            + " | "
            + perfeitos["ano"].astype(str)
            + "."
            + perfeitos["semestre"].astype(str)
        ).tolist()
        while len(descricoes) < 3:
            descricoes.append("Sem match perfeito adicional")
        top_match_1, top_match_2, top_match_3 = descricoes[:3]

    if divergencias.empty:
        top_div_1 = "Sem divergencias entre os matches"
        top_div_2 = "Sem divergencias entre os matches"
        top_div_3 = "Sem divergencias entre os matches"
    else:
        principais = divergencias.head(3)
        descricoes_div = (
            principais["unidade_canonica"]
            + " | "
            + principais["curso_canonico"]
            + " | diff_acum="
            + principais["diferenca_acumulado"].round(6).astype(str)
        ).tolist()
        while len(descricoes_div) < 3:
            descricoes_div.append("Sem divergencia adicional")
        top_div_1, top_div_2, top_div_3 = descricoes_div[:3]

    observacao = (
        "Sem interseccao nas chaves obrigatorias entre pipeline e gabarito."
        if matches.empty
        else "Comparacao realizada apenas sobre coortes completas com acumulado calculado."
    )

    return pd.DataFrame(
        [
            {
                "total_pipeline_filtrado": len(df_pipeline),
                "total_gabarito_filtrado": len(df_gabarito),
                "total_comparado": len(matches),
                "total_divergencias": len(divergencias),
                "total_sem_match_pipeline": len(sem_match_pipeline),
                "total_sem_match_gabarito": len(sem_match_gabarito),
                "aderencia_op2": percentual_flags(matches, "flag_match_op2"),
                "aderencia_op3": percentual_flags(matches, "flag_match_op3"),
                "aderencia_op4": percentual_flags(matches, "flag_match_op4"),
                "aderencia_acumulado": percentual_flags(matches, "flag_match_acumulado"),
                "aderencia_nivel": percentual_flags(matches, "flag_match_nivel"),
                "aderencia_diagnostico": percentual_flags(matches, "flag_match_diagnostico"),
                "tolerancia_absoluta": TOLERANCIA,
                "top_match_1": top_match_1,
                "top_match_2": top_match_2,
                "top_match_3": top_match_3,
                "top_divergencia_1": top_div_1,
                "top_divergencia_2": top_div_2,
                "top_divergencia_3": top_div_3,
                "observacao": observacao,
            }
        ]
    )


def exportar_abas(relatorio: dict[str, pd.DataFrame]) -> None:
    ARQ_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        for nome_aba, tabela in relatorio.items():
            tabela.to_excel(writer, sheet_name=nome_aba, index=False)


def main() -> None:
    ref_cursos, ref_unidades, ref_periodo = carregar_referencias()
    pipeline = carregar_pipeline()
    gabarito = carregar_gabarito(ref_cursos, ref_unidades, ref_periodo)
    matches = montar_matches(pipeline, gabarito)
    divergencias = montar_divergencias(matches)
    sem_match_pipeline = montar_sem_match_pipeline(pipeline, matches)
    sem_match_gabarito = montar_sem_match_gabarito(gabarito, matches)
    resumo = montar_resumo(
        pipeline,
        gabarito,
        matches,
        divergencias,
        sem_match_pipeline,
        sem_match_gabarito,
    )

    relatorio = {
        "matches": matches,
        "divergencias": divergencias,
        "sem_match_pipeline": sem_match_pipeline,
        "sem_match_gabarito": sem_match_gabarito,
        "resumo_validacao": resumo,
    }
    exportar_abas(relatorio)

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    main()
