from __future__ import annotations

from pathlib import Path
import sys
import unicodedata

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from ared.normalizar import normalizar_texto  # noqa: E402


ARQ_STAGING = RAIZ_PROJETO / "saida/staging/stg_vestibulinho_normalizado.xlsx"
DIR_SAIDA = RAIZ_PROJETO / "saida/curated"
ARQ_FATO = DIR_SAIDA / "fato_vestibulinho_oferta_semestre.xlsx"
ARQ_RELATORIO = DIR_SAIDA / "RELATORIO_CURATED_VESTIBULINHO.xlsx"


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


def gerar_chave_oferta_semestre(df: pd.DataFrame) -> pd.Series:
    partes = [
        df["ano_referencia"].astype(str),
        df["semestre_referencia"].astype(str),
        df["codigo_unidade_raw"].map(normalizar_texto),
        df["codigo_unidade_canonico"].map(normalizar_texto),
        df["tipo_local_oferta"].map(normalizar_texto),
        df["curso_raw"].map(normalizar_texto),
        df["curso_canonico"].map(normalizar_texto),
        df["periodo_canonico"].map(normalizar_texto),
        df["tipo_ensino"].map(normalizar_texto),
    ]
    chave = partes[0]
    for parte in partes[1:]:
        chave = chave + "|" + parte
    return chave


def montar_curated(df_staging: pd.DataFrame) -> pd.DataFrame:
    colunas = {
        "ano_referencia": resolver_coluna(df_staging, "ano_referencia"),
        "semestre_referencia": resolver_coluna(df_staging, "semestre_referencia"),
        "codigo_unidade_raw": resolver_coluna(df_staging, "Código"),
        "nome_unidade_raw": resolver_coluna(df_staging, "Unidades do CEETEPS"),
        "codigo_unidade_canonico": resolver_coluna(df_staging, "codigo_unidade_canonico"),
        "nome_unidade_canonico": resolver_coluna(df_staging, "nome_unidade_canonico"),
        "curso_raw": resolver_coluna(df_staging, "Curso/Habilitação"),
        "curso_canonico": resolver_coluna(df_staging, "curso_canonico"),
        "periodo_canonico": resolver_coluna(df_staging, "periodo_canonico"),
        "cod_periodo_ared": resolver_coluna(df_staging, "cod_periodo_ared"),
        "tipo_local_oferta": resolver_coluna(df_staging, "tipo_local_oferta"),
        "tipo_ensino": resolver_coluna(df_staging, "Tipo de Ensino"),
        "codigo_curso_raw": resolver_coluna(df_staging, "Curso/Habilitação"),
        "vagas": resolver_coluna(df_staging, "Vagas"),
        "inscritos": resolver_coluna(df_staging, "Inscritos"),
        "demanda": resolver_coluna(df_staging, "Demanda"),
    }

    curated = df_staging[[colunas[coluna] for coluna in colunas]].copy()
    curated.columns = list(colunas.keys())

    for coluna in ["ano_referencia", "semestre_referencia", "vagas", "inscritos"]:
        curated[coluna] = pd.to_numeric(curated[coluna], errors="coerce")

    curated["demanda"] = (
        curated["demanda"]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    curated["demanda"] = pd.to_numeric(curated["demanda"], errors="coerce")

    curated["chave_oferta_semestre"] = gerar_chave_oferta_semestre(curated)

    ordem_final = [
        "chave_oferta_semestre",
        "ano_referencia",
        "semestre_referencia",
        "codigo_unidade_raw",
        "nome_unidade_raw",
        "codigo_unidade_canonico",
        "nome_unidade_canonico",
        "curso_raw",
        "curso_canonico",
        "periodo_canonico",
        "cod_periodo_ared",
        "tipo_local_oferta",
        "tipo_ensino",
        "codigo_curso_raw",
        "vagas",
        "inscritos",
        "demanda",
    ]
    return curated[ordem_final]


def montar_relatorio(df_curated: pd.DataFrame) -> dict[str, pd.DataFrame]:
    resumo = pd.DataFrame(
        [
            {
                "linhas": len(df_curated),
                "colunas": len(df_curated.columns),
                "chaves_unicas": df_curated["chave_oferta_semestre"].nunique(),
            }
        ]
    )

    colunas_finais = pd.DataFrame({"coluna": list(df_curated.columns)})

    duplicidades = df_curated[df_curated["chave_oferta_semestre"].duplicated(keep=False)].copy()
    cardinalidade = pd.DataFrame(
        [
            {
                "linhas": len(df_curated),
                "chaves_unicas": df_curated["chave_oferta_semestre"].nunique(),
                "duplicidades": len(duplicidades),
            }
        ]
    )

    contagem_tipo_ensino = (
        df_curated["tipo_ensino"]
        .value_counts(dropna=False)
        .rename_axis("tipo_ensino")
        .reset_index(name="quantidade")
    )

    contagem_periodo = (
        df_curated["periodo_canonico"]
        .value_counts(dropna=False)
        .rename_axis("periodo_canonico")
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

    distribuicao_demanda = (
        df_curated["demanda"]
        .describe()
        .rename_axis("estatistica")
        .reset_index(name="valor")
    )

    cursos_maior_demanda = (
        df_curated.sort_values("demanda", ascending=False)[
            ["curso_canonico", "nome_unidade_canonico", "periodo_canonico", "tipo_ensino", "demanda"]
        ]
        .head(20)
        .reset_index(drop=True)
    )

    return {
        "resumo": resumo,
        "colunas_finais": colunas_finais,
        "cardinalidade_chave": cardinalidade,
        "duplicidades": duplicidades,
        "contagem_tipo_ensino": contagem_tipo_ensino,
        "contagem_periodo": contagem_periodo,
        "top_cursos": top_cursos,
        "top_unidades": top_unidades,
        "distribuicao_demanda": distribuicao_demanda,
        "cursos_maior_demanda": cursos_maior_demanda,
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
    print(f"Chaves únicas: {df_curated['chave_oferta_semestre'].nunique()}")
    print(f"Duplicidades: {duplicidades}")


if __name__ == "__main__":
    main()
