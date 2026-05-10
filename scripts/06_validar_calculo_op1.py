from __future__ import annotations

from pathlib import Path
import sys
import unicodedata

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from ared.normalizar import normalizar_texto  # noqa: E402


ARQ_VEST = RAIZ_PROJETO / "saida/curated/fato_vestibulinho_oferta_semestre.xlsx"
ARQ_ALUNOS = RAIZ_PROJETO / "saida/curated/fato_alunos_turma_semestre.xlsx"
ARQ_MATCHES = RAIZ_PROJETO / "saida/validacao/VALIDACAO_COORTES_ENTRADA.xlsx"
ARQ_GABARITO_2026_1 = RAIZ_PROJETO / "saida/GABARITO_ARED_2026_1.xlsx"
ARQ_GABARITO_2026_2 = RAIZ_PROJETO / "saida/GABARITO_ARED_2026_2.xlsx"
DIR_SAIDA = RAIZ_PROJETO / "saida/validacao"
ARQ_SAIDA = DIR_SAIDA / "VALIDACAO_OP1.xlsx"


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


def carregar_dados() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    vest = pd.read_excel(ARQ_VEST)
    alunos = pd.read_excel(ARQ_ALUNOS)
    matches = pd.read_excel(ARQ_MATCHES, sheet_name="matches")
    gabarito_2026_1 = pd.read_excel(ARQ_GABARITO_2026_1)
    gabarito_2026_2 = pd.read_excel(ARQ_GABARITO_2026_2) if ARQ_GABARITO_2026_2.exists() else None
    return vest, alunos, matches, gabarito_2026_1, gabarito_2026_2


def preparar_matches(df_matches: pd.DataFrame) -> pd.DataFrame:
    df = df_matches.copy()
    df["join_key"] = (
        df["codigo_unidade_canonico_chave"].map(normalizar_texto)
        + "|"
        + df["curso_canonico_chave"].map(normalizar_texto)
        + "|"
        + df["periodo_canonico_chave"].map(normalizar_texto)
        + "|"
        + df["tipo_ensino_chave"].map(normalizar_texto)
        + "|"
        + df["tipo_local_oferta_chave"].map(normalizar_texto)
    )
    return df


def preparar_facts(vest: pd.DataFrame, alunos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    col_flag_entrada = resolver_coluna(alunos, "flag_entrada")
    alunos_entrada = alunos[alunos[col_flag_entrada].map(normalizar_texto) == "SIM"].copy()
    alunos_entrada["join_key"] = (
        alunos_entrada["codigo_unidade_canonico"].map(normalizar_texto)
        + "|"
        + alunos_entrada["curso_canonico"].map(normalizar_texto)
        + "|"
        + alunos_entrada["periodo_canonico"].map(normalizar_texto)
        + "|"
        + alunos_entrada["tipo_ensino"].map(normalizar_texto)
        + "|"
        + alunos_entrada["tipo_local_oferta"].map(normalizar_texto)
    )

    vest["join_key"] = (
        vest["codigo_unidade_canonico"].map(normalizar_texto)
        + "|"
        + vest["curso_canonico"].map(normalizar_texto)
        + "|"
        + vest["periodo_canonico"].map(normalizar_texto)
        + "|"
        + vest["tipo_ensino"].map(normalizar_texto)
        + "|"
        + vest["tipo_local_oferta"].map(normalizar_texto)
    )
    return vest, alunos_entrada


def preparar_gabarito_2026_1(df: pd.DataFrame) -> pd.DataFrame:
    col_codigo_unidade = resolver_coluna(df, "Cód Unidade")
    col_curso = resolver_coluna(df, "Habilitação/Curso")
    col_periodo = resolver_coluna(df, "Período")
    col_vagas = resolver_coluna(df, "Vagas")
    col_op1 = resolver_coluna(df, "Op 1")
    col_pct = resolver_coluna(df, "%")

    gb = df[[col_codigo_unidade, col_curso, col_periodo, col_vagas, col_op1, col_pct]].copy()
    gb.columns = ["codigo_unidade_gabarito", "curso_raw_gabarito", "periodo_gabarito", "vagas_esperado", "op1_esperado", "op1_percentual_esperado"]
    gb["codigo_unidade_gabarito"] = gb["codigo_unidade_gabarito"].map(lambda v: normalizar_texto(v).zfill(3) if normalizar_texto(v).isdigit() else normalizar_texto(v))
    gb["curso_canonico_gabarito"] = gb["curso_raw_gabarito"].map(normalizar_texto)
    gb["periodo_canonico_gabarito"] = gb["periodo_gabarito"].map(normalizar_texto)
    gb["vagas_esperado"] = pd.to_numeric(gb["vagas_esperado"], errors="coerce")
    gb["op1_esperado"] = pd.to_numeric(gb["op1_esperado"], errors="coerce")
    gb["op1_percentual_esperado"] = pd.to_numeric(gb["op1_percentual_esperado"], errors="coerce")
    gb["gabarito_key"] = (
        gb["codigo_unidade_gabarito"]
        + "|"
        + gb["curso_canonico_gabarito"]
        + "|"
        + gb["periodo_canonico_gabarito"]
    )
    return gb


def montar_validacao_op1(
    vest: pd.DataFrame,
    alunos_entrada: pd.DataFrame,
    matches: pd.DataFrame,
    gabarito_2026_1: pd.DataFrame,
) -> pd.DataFrame:
    cols_vest = [
        "join_key",
        "codigo_unidade_canonico",
        "curso_raw",
        "curso_canonico",
        "periodo_canonico",
        "tipo_ensino",
        "tipo_local_oferta",
        "vagas",
        "inscritos",
        "demanda",
    ]
    cols_alunos = [
        "join_key",
        "numero_turma",
        "turma_raw",
        "tipo_etapa",
        "ordem_etapa",
        "flag_entrada",
        "total_alunos",
    ]

    base = matches[["join_key"]].drop_duplicates()
    base = base.merge(vest[cols_vest], on="join_key", how="left")
    base = base.merge(alunos_entrada[cols_alunos], on="join_key", how="left")

    base["op1_calculado"] = pd.to_numeric(base["total_alunos"], errors="coerce")
    base["vagas_calculado"] = pd.to_numeric(base["vagas"], errors="coerce")
    base["op1_percentual_calculado"] = (
        base["op1_calculado"] - base["vagas_calculado"]
    ) / base["vagas_calculado"]

    base["gabarito_key"] = (
        base["codigo_unidade_canonico"].map(lambda v: normalizar_texto(v).zfill(3) if normalizar_texto(v).isdigit() else normalizar_texto(v))
        + "|"
        + base["curso_canonico"].map(normalizar_texto)
        + "|"
        + base["periodo_canonico"].map(normalizar_texto)
    )

    comparacao = base.merge(
        gabarito_2026_1[
            [
                "gabarito_key",
                "curso_raw_gabarito",
                "vagas_esperado",
                "op1_esperado",
                "op1_percentual_esperado",
            ]
        ],
        on="gabarito_key",
        how="left",
    )

    comparacao["diferenca_op1"] = comparacao["op1_calculado"] - comparacao["op1_esperado"]
    comparacao["diferenca_percentual"] = (
        comparacao["op1_percentual_calculado"] - comparacao["op1_percentual_esperado"]
    )
    comparacao["arredondamento_ok_2_casas"] = (
        comparacao["op1_percentual_calculado"].round(2) == comparacao["op1_percentual_esperado"].round(2)
    )
    comparacao["aderente_exato"] = (
        comparacao["op1_calculado"].eq(comparacao["op1_esperado"])
        & comparacao["op1_percentual_calculado"].round(6).eq(comparacao["op1_percentual_esperado"].round(6))
    )
    comparacao["aderente_2_casas"] = (
        comparacao["op1_calculado"].eq(comparacao["op1_esperado"])
        & comparacao["arredondamento_ok_2_casas"]
    )

    comparacao["hipotese_formula"] = "OP1_PERCENTUAL = (Op1 - Vagas) / Vagas"
    comparacao["caso_especial"] = ""
    comparacao.loc[comparacao["curso_raw"] != comparacao["curso_raw_gabarito"], "caso_especial"] = (
        "Divergencia entre curso_raw e representacao do gabarito"
    )
    comparacao.loc[comparacao["tipo_local_oferta"] != "ETEC", "caso_especial"] = comparacao["caso_especial"].mask(
        comparacao["tipo_local_oferta"] != "ETEC",
        comparacao["caso_especial"].where(
            comparacao["caso_especial"] == "",
            comparacao["caso_especial"] + " | "
        ) + "Oferta com tipo_local_oferta especial",
    )

    return comparacao


def montar_relatorio(validacao: pd.DataFrame, gabarito_2026_2_disponivel: bool) -> dict[str, pd.DataFrame]:
    comparaveis = validacao[validacao["op1_esperado"].notna()].copy()
    qtd_validada = len(comparaveis)
    aderentes = int(comparaveis["aderente_2_casas"].sum())
    percentual_aderencia = (aderentes / qtd_validada) if qtd_validada else 0.0

    resumo = pd.DataFrame(
        [
            {
                "quantidade_matches_analisados": len(validacao),
                "quantidade_validada_contra_gabarito": qtd_validada,
                "aderentes_2_casas": aderentes,
                "percentual_aderencia": percentual_aderencia,
                "amostra_2026_2_disponivel": "SIM" if gabarito_2026_2_disponivel else "NAO",
            }
        ]
    )

    maiores_divergencias = comparaveis.reindex(
        comparaveis["diferenca_percentual"].abs().sort_values(ascending=False).index
    ).head(20)

    exemplos_corretos = comparaveis[comparaveis["aderente_2_casas"]].head(20)

    hipotese_final = pd.DataFrame(
        [
            {
                "hipotese_formula": "OP1_PERCENTUAL = (Op1 - Vagas) / Vagas",
                "base_evidencia": "Gabarito ARED 2026.1 disponível localmente",
                "status_2026_2": "Sem amostra local para validação" if not gabarito_2026_2_disponivel else "Amostra local disponível",
                "observacao": "Validação baseada em coortes com match entre vestibulinho e turmas de entrada.",
            }
        ]
    )

    return {
        "resumo": resumo,
        "validacao_op1": validacao,
        "maiores_divergencias": maiores_divergencias,
        "exemplos_corretos": exemplos_corretos,
        "hipotese_final": hipotese_final,
    }


def exportar(relatorio: dict[str, pd.DataFrame]) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        for nome_aba, tabela in relatorio.items():
            tabela.to_excel(writer, sheet_name=nome_aba, index=False)


def main() -> None:
    vest, alunos, matches, gabarito_2026_1, gabarito_2026_2 = carregar_dados()
    matches = preparar_matches(matches)
    vest, alunos_entrada = preparar_facts(vest, alunos)
    gabarito_2026_1 = preparar_gabarito_2026_1(gabarito_2026_1)

    validacao = montar_validacao_op1(vest, alunos_entrada, matches, gabarito_2026_1)
    relatorio = montar_relatorio(validacao, gabarito_2026_2 is not None)
    exportar(relatorio)

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(relatorio["resumo"].to_string(index=False))


if __name__ == "__main__":
    main()
