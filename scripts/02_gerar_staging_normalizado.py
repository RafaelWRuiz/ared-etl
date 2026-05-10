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
    normalizar_etapa,
    normalizar_periodo,
    normalizar_texto,
    normalizar_unidade,
)


ARQ_ALUNOS = RAIZ_PROJETO / "dados_brutos/alunos/totais_alunos_1sem2026.csv"
ARQ_VESTIBULINHO = RAIZ_PROJETO / "dados_brutos/vestibulinho/1sem2026.csv"

ARQ_REF_CURSOS = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_curso.xlsx"
ARQ_REF_UNIDADES = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_unidade.xlsx"
ARQ_REF_PERIODO = RAIZ_PROJETO / "dados_brutos/referencias/ref_periodo.xlsx"
ARQ_REF_ETAPA = RAIZ_PROJETO / "dados_brutos/referencias/ref_etapa_turma.xlsx"

DIR_SAIDA = RAIZ_PROJETO / "saida/staging"
ARQ_STG_ALUNOS = DIR_SAIDA / "stg_alunos_normalizado.xlsx"
ARQ_STG_VESTIBULINHO = DIR_SAIDA / "stg_vestibulinho_normalizado.xlsx"
ARQ_RELATORIO = DIR_SAIDA / "RELATORIO_NORMALIZACAO.xlsx"

ANO_REFERENCIA = 2026
SEMESTRE_REFERENCIA = 1


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


def carregar_csv(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, sep=";", encoding="latin1", index_col=False)
    df = df.loc[:, ~df.columns.isna()]
    df.columns = [normalizar_texto(coluna) for coluna in df.columns]
    df = df.loc[:, [coluna for coluna in df.columns if coluna]]

    colunas_vazias = [
        coluna
        for coluna in df.columns
        if df[coluna].isna().all()
        or df[coluna].map(lambda valor: normalizar_texto(valor) == "").all()
    ]
    if colunas_vazias:
        df = df.drop(columns=colunas_vazias)

    for coluna in df.select_dtypes(include=["object", "string"]).columns:
        df[coluna] = df[coluna].map(normalizar_texto)

    return df


def carregar_referencias() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ref_cursos = pd.read_excel(ARQ_REF_CURSOS, sheet_name="ref_mapeamento_curso")
    ref_unidades = pd.read_excel(ARQ_REF_UNIDADES, sheet_name="ref_mapeamento_unidade")
    ref_periodo = pd.read_excel(ARQ_REF_PERIODO, sheet_name="ref_periodo")
    ref_etapa = pd.read_excel(ARQ_REF_ETAPA, sheet_name="ref_etapa_turma")
    return ref_cursos, ref_unidades, ref_periodo, ref_etapa


def adicionar_metadados(df: pd.DataFrame, arquivo_origem: str) -> pd.DataFrame:
    df["arquivo_origem"] = arquivo_origem
    df["ano_referencia"] = ANO_REFERENCIA
    df["semestre_referencia"] = SEMESTRE_REFERENCIA
    return df


def value_to_bool_text(valor: bool) -> str:
    return "SIM" if valor else "NAO"


def nullable_bool_to_text(valor: bool | None) -> str:
    if valor is None:
        return "REVISAR"
    return "SIM" if valor else "NAO"


def normalizar_df_alunos(
    df: pd.DataFrame,
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
    ref_etapa: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    col_curso = resolver_coluna(df, "Habilitação/Curso")
    col_codigo_unidade = resolver_coluna(df, "Código da Unidade")
    col_nome_unidade = resolver_coluna(df, "Unidades do CEETEPS")
    col_periodo = resolver_coluna(df, "Período")
    col_turma = resolver_coluna(df, "Turma")

    cursos = df[col_curso].map(lambda valor: normalizar_curso(valor, ref_cursos))
    df["curso_canonico"] = cursos.map(lambda valor: valor["curso_canonico"])
    df["flag_mtec"] = cursos.map(lambda valor: valor["flag_mtec"])
    df["flag_mtec_pi"] = cursos.map(lambda valor: valor["flag_mtec_pi"])
    df["flag_ams"] = cursos.map(lambda valor: valor["flag_ams"])
    df["flag_mnp"] = cursos.map(lambda valor: valor["flag_mnp"])
    df["flag_ead"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_ead"]))
    df["flag_curso_nao_mapeado"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_nao_mapeado"]))

    unidades = df.apply(
        lambda linha: normalizar_unidade(
            codigo_raw=linha[col_codigo_unidade],
            nome_raw=linha[col_nome_unidade],
            ref_unidades_df=ref_unidades,
        ),
        axis=1,
    )
    df["codigo_unidade_canonico"] = unidades.map(lambda valor: valor["codigo_unidade_canonico"])
    df["nome_unidade_canonico"] = unidades.map(lambda valor: valor["nome_unidade_canonico"])
    df["tipo_local_oferta"] = unidades.map(lambda valor: valor["tipo_local_oferta"])
    df["flag_unidade_nao_mapeada"] = unidades.map(
        lambda valor: value_to_bool_text(valor["flag_nao_mapeado"])
    )

    periodos = df[col_periodo].map(lambda valor: normalizar_periodo(valor, ref_periodo))
    df["periodo_canonico"] = periodos.map(lambda valor: valor["periodo_canonico"])
    df["cod_periodo_ared"] = periodos.map(lambda valor: valor["cod_periodo_ared"])
    df["flag_periodo_nao_mapeado"] = periodos.map(
        lambda valor: value_to_bool_text(
            valor["flag_nao_mapeado"] or normalizar_texto(valor["cod_periodo_ared"]) == "REVISAR"
        )
    )

    etapas = df[col_turma].map(lambda valor: normalizar_etapa(valor, ref_etapa))
    df["tipo_etapa"] = etapas.map(lambda valor: valor["tipo_etapa"])
    df["ordem_etapa"] = etapas.map(lambda valor: valor["ordem_etapa"])
    df["flag_entrada"] = etapas.map(lambda valor: nullable_bool_to_text(valor["flag_entrada"]))
    df["flag_etapa_nao_mapeada"] = etapas.map(
        lambda valor: value_to_bool_text(valor["flag_nao_mapeado"])
    )

    return adicionar_metadados(df, ARQ_ALUNOS.name)


def normalizar_df_vestibulinho(
    df: pd.DataFrame,
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    col_curso = resolver_coluna(df, "Curso/Habilitação")
    col_codigo = resolver_coluna(df, "Código")
    col_nome_unidade = resolver_coluna(df, "Unidades do CEETEPS")
    col_periodo = resolver_coluna(df, "Período")

    cursos = df[col_curso].map(lambda valor: normalizar_curso(valor, ref_cursos))
    df["curso_canonico"] = cursos.map(lambda valor: valor["curso_canonico"])
    df["flag_mtec"] = cursos.map(lambda valor: valor["flag_mtec"])
    df["flag_mtec_pi"] = cursos.map(lambda valor: valor["flag_mtec_pi"])
    df["flag_ams"] = cursos.map(lambda valor: valor["flag_ams"])
    df["flag_mnp"] = cursos.map(lambda valor: valor["flag_mnp"])
    df["flag_ead"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_ead"]))
    df["flag_curso_nao_mapeado"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_nao_mapeado"]))

    unidades = df.apply(
        lambda linha: normalizar_unidade(
            codigo_raw=linha[col_codigo],
            nome_raw=linha[col_nome_unidade],
            ref_unidades_df=ref_unidades,
        ),
        axis=1,
    )
    df["codigo_unidade_canonico"] = unidades.map(lambda valor: valor["codigo_unidade_canonico"])
    df["nome_unidade_canonico"] = unidades.map(lambda valor: valor["nome_unidade_canonico"])
    df["tipo_local_oferta"] = unidades.map(lambda valor: valor["tipo_local_oferta"])
    df["flag_unidade_nao_mapeada"] = unidades.map(
        lambda valor: value_to_bool_text(valor["flag_nao_mapeado"])
    )

    periodos = df[col_periodo].map(lambda valor: normalizar_periodo(valor, ref_periodo))
    df["periodo_canonico"] = periodos.map(lambda valor: valor["periodo_canonico"])
    df["cod_periodo_ared"] = periodos.map(lambda valor: valor["cod_periodo_ared"])
    df["flag_periodo_nao_mapeado"] = periodos.map(
        lambda valor: value_to_bool_text(
            valor["flag_nao_mapeado"] or normalizar_texto(valor["cod_periodo_ared"]) == "REVISAR"
        )
    )

    return adicionar_metadados(df, ARQ_VESTIBULINHO.name)


def montar_resumo_bases(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"base": "ALUNOS", "linhas": len(df_alunos)},
            {"base": "VESTIBULINHO", "linhas": len(df_vest)},
        ]
    )


def consolidar_nao_mapeados(
    df_alunos: pd.DataFrame,
    df_vest: pd.DataFrame,
    coluna_flag: str,
    coluna_valor_alunos: str,
    coluna_valor_vest: str,
    nome_coluna_saida: str,
) -> pd.DataFrame:
    coluna_alunos = resolver_coluna(df_alunos, coluna_valor_alunos)
    coluna_vest = resolver_coluna(df_vest, coluna_valor_vest)

    alunos = (
        df_alunos[df_alunos[coluna_flag] == "SIM"][coluna_alunos]
        .value_counts(dropna=False)
        .rename_axis(nome_coluna_saida)
        .reset_index(name="quantidade")
    )
    if not alunos.empty:
        alunos["base"] = "ALUNOS"

    vest = (
        df_vest[df_vest[coluna_flag] == "SIM"][coluna_vest]
        .value_counts(dropna=False)
        .rename_axis(nome_coluna_saida)
        .reset_index(name="quantidade")
    )
    if not vest.empty:
        vest["base"] = "VESTIBULINHO"

    return pd.concat([alunos, vest], ignore_index=True)


def consolidar_nao_mapeados_alunos(
    df_alunos: pd.DataFrame,
    coluna_flag: str,
    coluna_valor: str,
    nome_coluna_saida: str,
) -> pd.DataFrame:
    coluna = resolver_coluna(df_alunos, coluna_valor)
    return (
        df_alunos[df_alunos[coluna_flag] == "SIM"][coluna]
        .value_counts(dropna=False)
        .rename_axis(nome_coluna_saida)
        .reset_index(name="quantidade")
    )


def montar_contagem_tipo_etapa(df_alunos: pd.DataFrame) -> pd.DataFrame:
    return (
        df_alunos["tipo_etapa"]
        .value_counts(dropna=False)
        .rename_axis("tipo_etapa")
        .reset_index(name="quantidade")
    )


def montar_contagem_periodo_canonico(
    df_alunos: pd.DataFrame,
    df_vest: pd.DataFrame,
) -> pd.DataFrame:
    base_alunos = (
        df_alunos["periodo_canonico"]
        .value_counts(dropna=False)
        .rename_axis("periodo_canonico")
        .reset_index(name="quantidade")
    )
    base_alunos["base"] = "ALUNOS"

    base_vest = (
        df_vest["periodo_canonico"]
        .value_counts(dropna=False)
        .rename_axis("periodo_canonico")
        .reset_index(name="quantidade")
    )
    base_vest["base"] = "VESTIBULINHO"

    return pd.concat([base_alunos, base_vest], ignore_index=True)


def gerar_relatorio(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> None:
    resumo_bases = montar_resumo_bases(df_alunos, df_vest)
    cursos_nao_mapeados = consolidar_nao_mapeados(
        df_alunos,
        df_vest,
        coluna_flag="flag_curso_nao_mapeado",
        coluna_valor_alunos="Habilitação/Curso",
        coluna_valor_vest="Curso/Habilitação",
        nome_coluna_saida="curso_raw",
    )
    unidades_nao_mapeadas = consolidar_nao_mapeados(
        df_alunos,
        df_vest,
        coluna_flag="flag_unidade_nao_mapeada",
        coluna_valor_alunos="Unidades do CEETEPS",
        coluna_valor_vest="Unidades do CEETEPS",
        nome_coluna_saida="unidade_raw",
    )
    periodos_nao_mapeados = consolidar_nao_mapeados(
        df_alunos,
        df_vest,
        coluna_flag="flag_periodo_nao_mapeado",
        coluna_valor_alunos="Período",
        coluna_valor_vest="Período",
        nome_coluna_saida="periodo_raw",
    )
    etapas_nao_mapeadas = consolidar_nao_mapeados_alunos(
        df_alunos,
        coluna_flag="flag_etapa_nao_mapeada",
        coluna_valor="Turma",
        nome_coluna_saida="turma_raw",
    )
    contagem_tipo_etapa = montar_contagem_tipo_etapa(df_alunos)
    contagem_periodo_canonico = montar_contagem_periodo_canonico(df_alunos, df_vest)

    with pd.ExcelWriter(ARQ_RELATORIO, engine="openpyxl") as writer:
        resumo_bases.to_excel(writer, sheet_name="resumo_bases", index=False)
        cursos_nao_mapeados.to_excel(writer, sheet_name="cursos_nao_mapeados", index=False)
        unidades_nao_mapeadas.to_excel(writer, sheet_name="unidades_nao_mapeadas", index=False)
        periodos_nao_mapeados.to_excel(writer, sheet_name="periodos_nao_mapeados", index=False)
        etapas_nao_mapeadas.to_excel(writer, sheet_name="etapas_nao_mapeadas", index=False)
        contagem_tipo_etapa.to_excel(writer, sheet_name="contagem_tipo_etapa", index=False)
        contagem_periodo_canonico.to_excel(
            writer,
            sheet_name="contagem_periodo_canonico",
            index=False,
        )


def exportar_staging(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    df_alunos.to_excel(ARQ_STG_ALUNOS, index=False)
    df_vest.to_excel(ARQ_STG_VESTIBULINHO, index=False)


def main() -> None:
    ref_cursos, ref_unidades, ref_periodo, ref_etapa = carregar_referencias()

    df_alunos = carregar_csv(ARQ_ALUNOS)
    df_vest = carregar_csv(ARQ_VESTIBULINHO)

    df_alunos_normalizado = normalizar_df_alunos(
        df_alunos,
        ref_cursos=ref_cursos,
        ref_unidades=ref_unidades,
        ref_periodo=ref_periodo,
        ref_etapa=ref_etapa,
    )
    df_vest_normalizado = normalizar_df_vestibulinho(
        df_vest,
        ref_cursos=ref_cursos,
        ref_unidades=ref_unidades,
        ref_periodo=ref_periodo,
    )

    exportar_staging(df_alunos_normalizado, df_vest_normalizado)
    gerar_relatorio(df_alunos_normalizado, df_vest_normalizado)

    print(f"Arquivo gerado: {ARQ_STG_ALUNOS}")
    print(f"Arquivo gerado: {ARQ_STG_VESTIBULINHO}")
    print(f"Arquivo gerado: {ARQ_RELATORIO}")
    print(f"Linhas alunos: {len(df_alunos_normalizado)}")
    print(f"Linhas vestibulinho: {len(df_vest_normalizado)}")


if __name__ == "__main__":
    main()
