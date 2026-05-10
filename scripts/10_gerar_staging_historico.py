from __future__ import annotations

from pathlib import Path
import re
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


DIR_ALUNOS = RAIZ_PROJETO / "dados_brutos/alunos"
DIR_VESTIBULINHO = RAIZ_PROJETO / "dados_brutos/vestibulinho"

ARQ_REF_CURSOS = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_curso.xlsx"
ARQ_REF_UNIDADES = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_unidade.xlsx"
ARQ_REF_PERIODO = RAIZ_PROJETO / "dados_brutos/referencias/ref_periodo.xlsx"
ARQ_REF_ETAPA = RAIZ_PROJETO / "dados_brutos/referencias/ref_etapa_turma.xlsx"

DIR_SAIDA = RAIZ_PROJETO / "saida/staging_historico"
ARQ_STG_ALUNOS = DIR_SAIDA / "stg_alunos_historico.xlsx"
ARQ_STG_VESTIBULINHO = DIR_SAIDA / "stg_vestibulinho_historico.xlsx"
ARQ_RELATORIO = DIR_SAIDA / "RELATORIO_STAGING_HISTORICO.xlsx"

REGEX_ALUNOS = re.compile(r"^totais_alunos_(?P<semestre>[12])sem(?P<ano>\d{4})\.csv$", re.IGNORECASE)
REGEX_VEST = re.compile(r"^(?P<semestre>[12])sem(?P<ano>\d{4})\.csv$", re.IGNORECASE)


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


def identificar_metadados(arquivo: Path, tipo_base: str) -> tuple[int, int]:
    regex = REGEX_ALUNOS if tipo_base == "ALUNOS" else REGEX_VEST
    match = regex.match(arquivo.name)
    if not match:
        raise ValueError(f"Nome de arquivo fora do padrão esperado: {arquivo.name}")
    return int(match.group("ano")), int(match.group("semestre"))


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


def adicionar_metadados(
    df: pd.DataFrame,
    *,
    tipo_base: str,
    ano_referencia: int,
    semestre_referencia: int,
    arquivo_origem: str,
) -> pd.DataFrame:
    df = df.copy()
    df["tipo_base"] = tipo_base
    df["ano_referencia"] = ano_referencia
    df["semestre_referencia"] = semestre_referencia
    df["periodo_referencia"] = f"{ano_referencia}.{semestre_referencia}"
    df["arquivo_origem"] = arquivo_origem
    return df


def value_to_bool_text(valor: bool) -> str:
    return "SIM" if valor else "NAO"


def nullable_bool_to_text(valor: bool | None) -> str:
    if valor is None:
        return "REVISAR"
    return "SIM" if valor else "NAO"


def normalizar_df_alunos(
    df: pd.DataFrame,
    *,
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
    ref_etapa: pd.DataFrame,
    ano_referencia: int,
    semestre_referencia: int,
    arquivo_origem: str,
) -> pd.DataFrame:
    df = df.copy()

    col_curso = resolver_coluna(df, "Habilitação/Curso")
    col_codigo_unidade = resolver_coluna(df, "Código da Unidade")
    col_nome_unidade = resolver_coluna(df, "Unidades do CEETEPS")
    col_periodo = resolver_coluna(df, "Período")
    col_turma = resolver_coluna(df, "Turma")

    cursos = df[col_curso].map(lambda valor: normalizar_curso(valor, ref_cursos))
    df["curso_canonico"] = cursos.map(lambda valor: valor["curso_canonico"])
    df["flag_mtec"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_mtec"]))
    df["flag_mtec_pi"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_mtec_pi"]))
    df["flag_ams"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_ams"]))
    df["flag_mnp"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_mnp"]))
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

    return adicionar_metadados(
        df,
        tipo_base="ALUNOS",
        ano_referencia=ano_referencia,
        semestre_referencia=semestre_referencia,
        arquivo_origem=arquivo_origem,
    )


def normalizar_df_vestibulinho(
    df: pd.DataFrame,
    *,
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
    ano_referencia: int,
    semestre_referencia: int,
    arquivo_origem: str,
) -> pd.DataFrame:
    df = df.copy()

    col_curso = resolver_coluna(df, "Curso/Habilitação")
    col_codigo = resolver_coluna(df, "Código")
    col_nome_unidade = resolver_coluna(df, "Unidades do CEETEPS")
    col_periodo = resolver_coluna(df, "Período")

    cursos = df[col_curso].map(lambda valor: normalizar_curso(valor, ref_cursos))
    df["curso_canonico"] = cursos.map(lambda valor: valor["curso_canonico"])
    df["flag_mtec"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_mtec"]))
    df["flag_mtec_pi"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_mtec_pi"]))
    df["flag_ams"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_ams"]))
    df["flag_mnp"] = cursos.map(lambda valor: value_to_bool_text(valor["flag_mnp"]))
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

    return adicionar_metadados(
        df,
        tipo_base="VESTIBULINHO",
        ano_referencia=ano_referencia,
        semestre_referencia=semestre_referencia,
        arquivo_origem=arquivo_origem,
    )


def consolidar_historico_alunos(
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
    ref_etapa: pd.DataFrame,
) -> pd.DataFrame:
    partes: list[pd.DataFrame] = []
    for caminho in sorted(DIR_ALUNOS.glob("*.csv")):
        ano_referencia, semestre_referencia = identificar_metadados(caminho, "ALUNOS")
        df = carregar_csv(caminho)
        partes.append(
            normalizar_df_alunos(
                df,
                ref_cursos=ref_cursos,
                ref_unidades=ref_unidades,
                ref_periodo=ref_periodo,
                ref_etapa=ref_etapa,
                ano_referencia=ano_referencia,
                semestre_referencia=semestre_referencia,
                arquivo_origem=caminho.name,
            )
        )
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def consolidar_historico_vestibulinho(
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
) -> pd.DataFrame:
    partes: list[pd.DataFrame] = []
    for caminho in sorted(DIR_VESTIBULINHO.glob("*.csv")):
        ano_referencia, semestre_referencia = identificar_metadados(caminho, "VESTIBULINHO")
        df = carregar_csv(caminho)
        partes.append(
            normalizar_df_vestibulinho(
                df,
                ref_cursos=ref_cursos,
                ref_unidades=ref_unidades,
                ref_periodo=ref_periodo,
                ano_referencia=ano_referencia,
                semestre_referencia=semestre_referencia,
                arquivo_origem=caminho.name,
            )
        )
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def montar_linhas_por_semestre(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> pd.DataFrame:
    base_alunos = (
        df_alunos.groupby(["periodo_referencia", "ano_referencia", "semestre_referencia"], dropna=False)
        .size()
        .reset_index(name="quantidade_linhas")
    )
    base_alunos["tipo_base"] = "ALUNOS"

    base_vest = (
        df_vest.groupby(["periodo_referencia", "ano_referencia", "semestre_referencia"], dropna=False)
        .size()
        .reset_index(name="quantidade_linhas")
    )
    base_vest["tipo_base"] = "VESTIBULINHO"

    return pd.concat([base_alunos, base_vest], ignore_index=True).sort_values(
        ["tipo_base", "ano_referencia", "semestre_referencia"]
    )


def montar_linhas_por_tipo_base(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"tipo_base": "ALUNOS", "quantidade_linhas": len(df_alunos)},
            {"tipo_base": "VESTIBULINHO", "quantidade_linhas": len(df_vest)},
        ]
    )


def montar_resumo_disponibilidade(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> pd.DataFrame:
    todos = pd.concat(
        [
            df_alunos[["tipo_base", "ano_referencia", "semestre_referencia", "periodo_referencia"]],
            df_vest[["tipo_base", "ano_referencia", "semestre_referencia", "periodo_referencia"]],
        ],
        ignore_index=True,
    )
    return pd.DataFrame(
        [
            {
                "anos_disponiveis": ", ".join(str(ano) for ano in sorted(todos["ano_referencia"].dropna().astype(int).unique())),
                "semestres_disponiveis": ", ".join(
                    str(semestre) for semestre in sorted(todos["semestre_referencia"].dropna().astype(int).unique())
                ),
                "periodos_disponiveis": ", ".join(sorted(todos["periodo_referencia"].dropna().astype(str).unique())),
            }
        ]
    )


def montar_contagem_tipo_etapa(df_alunos: pd.DataFrame) -> pd.DataFrame:
    return (
        df_alunos.groupby(["tipo_etapa"], dropna=False)
        .size()
        .reset_index(name="quantidade")
        .sort_values("quantidade", ascending=False)
    )


def montar_contagem_tipo_ensino(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> pd.DataFrame:
    base_alunos = (
        df_alunos.groupby(["tipo_ensino"], dropna=False)
        .size()
        .reset_index(name="quantidade")
    )
    base_alunos["tipo_base"] = "ALUNOS"

    base_vest = (
        df_vest.groupby(["tipo_ensino"], dropna=False)
        .size()
        .reset_index(name="quantidade")
    )
    base_vest["tipo_base"] = "VESTIBULINHO"

    return pd.concat([base_alunos, base_vest], ignore_index=True).sort_values(
        ["tipo_base", "quantidade"], ascending=[True, False]
    )


def montar_cursos_mais_frequentes(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> pd.DataFrame:
    base_alunos = (
        df_alunos.groupby(["curso_canonico"], dropna=False)
        .size()
        .reset_index(name="quantidade")
    )
    base_alunos["tipo_base"] = "ALUNOS"

    base_vest = (
        df_vest.groupby(["curso_canonico"], dropna=False)
        .size()
        .reset_index(name="quantidade")
    )
    base_vest["tipo_base"] = "VESTIBULINHO"

    return pd.concat([base_alunos, base_vest], ignore_index=True).sort_values(
        ["tipo_base", "quantidade"], ascending=[True, False]
    )


def montar_unidades_mais_frequentes(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> pd.DataFrame:
    base_alunos = (
        df_alunos.groupby(["nome_unidade_canonico"], dropna=False)
        .size()
        .reset_index(name="quantidade")
    )
    base_alunos["tipo_base"] = "ALUNOS"

    base_vest = (
        df_vest.groupby(["nome_unidade_canonico"], dropna=False)
        .size()
        .reset_index(name="quantidade")
    )
    base_vest["tipo_base"] = "VESTIBULINHO"

    return pd.concat([base_alunos, base_vest], ignore_index=True).sort_values(
        ["tipo_base", "quantidade"], ascending=[True, False]
    )


def montar_periodos_encontrados(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> pd.DataFrame:
    base_alunos = (
        df_alunos.groupby(["periodo_canonico"], dropna=False)
        .size()
        .reset_index(name="quantidade")
    )
    base_alunos["tipo_base"] = "ALUNOS"

    base_vest = (
        df_vest.groupby(["periodo_canonico"], dropna=False)
        .size()
        .reset_index(name="quantidade")
    )
    base_vest["tipo_base"] = "VESTIBULINHO"

    return pd.concat([base_alunos, base_vest], ignore_index=True).sort_values(
        ["tipo_base", "quantidade"], ascending=[True, False]
    )


def exportar_staging(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    df_alunos.to_excel(ARQ_STG_ALUNOS, index=False)
    df_vest.to_excel(ARQ_STG_VESTIBULINHO, index=False)


def gerar_relatorio(df_alunos: pd.DataFrame, df_vest: pd.DataFrame) -> None:
    linhas_por_semestre = montar_linhas_por_semestre(df_alunos, df_vest)
    linhas_por_tipo_base = montar_linhas_por_tipo_base(df_alunos, df_vest)
    resumo_disponibilidade = montar_resumo_disponibilidade(df_alunos, df_vest)
    contagem_tipo_etapa = montar_contagem_tipo_etapa(df_alunos)
    contagem_tipo_ensino = montar_contagem_tipo_ensino(df_alunos, df_vest)
    cursos_mais_frequentes = montar_cursos_mais_frequentes(df_alunos, df_vest)
    unidades_mais_frequentes = montar_unidades_mais_frequentes(df_alunos, df_vest)
    periodos_encontrados = montar_periodos_encontrados(df_alunos, df_vest)

    with pd.ExcelWriter(ARQ_RELATORIO, engine="openpyxl") as writer:
        linhas_por_semestre.to_excel(writer, sheet_name="linhas_por_semestre", index=False)
        linhas_por_tipo_base.to_excel(writer, sheet_name="linhas_por_tipo_base", index=False)
        resumo_disponibilidade.to_excel(writer, sheet_name="resumo_disponibilidade", index=False)
        contagem_tipo_etapa.to_excel(writer, sheet_name="contagem_tipo_etapa", index=False)
        contagem_tipo_ensino.to_excel(writer, sheet_name="contagem_tipo_ensino", index=False)
        cursos_mais_frequentes.to_excel(writer, sheet_name="cursos_mais_frequentes", index=False)
        unidades_mais_frequentes.to_excel(writer, sheet_name="unidades_mais_frequentes", index=False)
        periodos_encontrados.to_excel(writer, sheet_name="periodos_encontrados", index=False)


def main() -> None:
    ref_cursos, ref_unidades, ref_periodo, ref_etapa = carregar_referencias()

    df_alunos_historico = consolidar_historico_alunos(
        ref_cursos=ref_cursos,
        ref_unidades=ref_unidades,
        ref_periodo=ref_periodo,
        ref_etapa=ref_etapa,
    )
    df_vest_historico = consolidar_historico_vestibulinho(
        ref_cursos=ref_cursos,
        ref_unidades=ref_unidades,
        ref_periodo=ref_periodo,
    )

    exportar_staging(df_alunos_historico, df_vest_historico)
    gerar_relatorio(df_alunos_historico, df_vest_historico)

    print(f"Arquivo gerado: {ARQ_STG_ALUNOS}")
    print(f"Arquivo gerado: {ARQ_STG_VESTIBULINHO}")
    print(f"Arquivo gerado: {ARQ_RELATORIO}")
    print(f"Linhas alunos histórico: {len(df_alunos_historico)}")
    print(f"Linhas vestibulinho histórico: {len(df_vest_historico)}")


if __name__ == "__main__":
    main()
