from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from ared.regras_negocio import calcular_semestre_entrada, detectar_tipo_curso


ARQUIVO_MODELO = Path("dados_brutos/modelos/ARED_2026_1_MODELO.xlsx")
ABA_GABARITO = "Relatório ARED 2026.1"
PASTA_SAIDA = Path("saida")
ARQUIVO_GABARITO = PASTA_SAIDA / "GABARITO_ARED_2026_1.xlsx"
ARQUIVO_VALIDACAO = PASTA_SAIDA / "VALIDACAO_REGRAS_ARED_2026_1.xlsx"

SEMESTRE_FINAL = (2026, 1)
MAPA_MODULOS_POR_COORTE = {
    "2024.2": 2,
    "2024.1": 3,
    "2023.2": 4,
}


def extrair_gabarito() -> pd.DataFrame:
    PASTA_SAIDA.mkdir(exist_ok=True)

    df = pd.read_excel(
        ARQUIVO_MODELO,
        sheet_name=ABA_GABARITO,
        header=4,
    )
    df.to_excel(ARQUIVO_GABARITO, index=False)
    return df


def extrair_semestre_entrada(codigo_turma: object) -> str | None:
    correspondencia = re.match(r"^(\d{4}\.\d)", str(codigo_turma))
    if correspondencia:
        return correspondencia.group(1)
    return None


def inferir_quantidade_modulos(tipo_curso: str, semestre_entrada: str | None) -> int | None:
    if tipo_curso != "MODULAR":
        return None
    return MAPA_MODULOS_POR_COORTE.get(semestre_entrada)


def calcular_semestre_linha(tipo_curso: str, quantidade_modulos: int | None) -> str:
    if pd.isna(quantidade_modulos):
        quantidade_modulos = None
    elif quantidade_modulos is not None:
        quantidade_modulos = int(quantidade_modulos)

    return calcular_semestre_entrada(
        ano_referencia=SEMESTRE_FINAL[0],
        semestre_referencia=SEMESTRE_FINAL[1],
        tipo_curso=tipo_curso,
        quantidade_modulos=quantidade_modulos,
    )


def montar_validacao(df_gabarito: pd.DataFrame) -> pd.DataFrame:
    df = df_gabarito.copy()

    coluna_codigo_turma = df.columns[0]
    coluna_curso = df.columns[6]

    df["TIPO_CURSO"] = df[coluna_curso].apply(detectar_tipo_curso)
    df["SEMESTRE_ENTRADA_GABARITO"] = df[coluna_codigo_turma].apply(extrair_semestre_entrada)
    df["QUANTIDADE_MODULOS_INFERIDA"] = df.apply(
        lambda linha: inferir_quantidade_modulos(
            tipo_curso=linha["TIPO_CURSO"],
            semestre_entrada=linha["SEMESTRE_ENTRADA_GABARITO"],
        ),
        axis=1,
    )
    df["SEMESTRE_ENTRADA_CALCULADO"] = df.apply(
        lambda linha: calcular_semestre_linha(
            tipo_curso=linha["TIPO_CURSO"],
            quantidade_modulos=linha["QUANTIDADE_MODULOS_INFERIDA"],
        ),
        axis=1,
    )
    df["REGRA_CONFERE"] = (
        df["SEMESTRE_ENTRADA_GABARITO"] == df["SEMESTRE_ENTRADA_CALCULADO"]
    )

    return df


def montar_resumo(df_validacao: pd.DataFrame) -> pd.DataFrame:
    return (
        df_validacao.groupby(
            [
                "TIPO_CURSO",
                "SEMESTRE_ENTRADA_GABARITO",
                "QUANTIDADE_MODULOS_INFERIDA",
                "REGRA_CONFERE",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="QUANTIDADE_TURMAS")
        .sort_values(
            [
                "TIPO_CURSO",
                "SEMESTRE_ENTRADA_GABARITO",
                "QUANTIDADE_MODULOS_INFERIDA",
            ]
        )
    )


def exportar_validacao(df_gabarito: pd.DataFrame, df_validacao: pd.DataFrame) -> None:
    resumo = montar_resumo(df_validacao)
    inconsistencias = df_validacao[~df_validacao["REGRA_CONFERE"]].copy()

    with pd.ExcelWriter(ARQUIVO_VALIDACAO) as writer:
        df_gabarito.to_excel(writer, sheet_name="gabarito_extraido", index=False)
        df_validacao.to_excel(writer, sheet_name="validacao_regras", index=False)
        resumo.to_excel(writer, sheet_name="resumo", index=False)
        inconsistencias.to_excel(writer, sheet_name="inconsistencias", index=False)


def main() -> None:
    df_gabarito = extrair_gabarito()
    df_validacao = montar_validacao(df_gabarito)
    exportar_validacao(df_gabarito, df_validacao)

    total = len(df_validacao)
    total_ok = int(df_validacao["REGRA_CONFERE"].sum())
    total_erro = total - total_ok

    print(f"Gabarito extraido em: {ARQUIVO_GABARITO}")
    print(f"Validacao gerada em: {ARQUIVO_VALIDACAO}")
    print(f"Total de linhas: {total}")
    print(f"Linhas validadas: {total_ok}")
    print(f"Inconsistencias: {total_erro}")


if __name__ == "__main__":
    main()
