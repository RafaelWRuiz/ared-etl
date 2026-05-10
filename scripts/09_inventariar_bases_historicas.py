from __future__ import annotations

from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))


DIR_ALUNOS = RAIZ_PROJETO / "dados_brutos/alunos"
DIR_VESTIBULINHO = RAIZ_PROJETO / "dados_brutos/vestibulinho"
DIR_SAIDA = RAIZ_PROJETO / "saida/inventario"
ARQ_SAIDA = DIR_SAIDA / "INVENTARIO_BASES_HISTORICAS.xlsx"

REGEX_ALUNOS = re.compile(r"^totais_alunos_(?P<semestre>[12])sem(?P<ano>\d{4})\.csv$", re.IGNORECASE)
REGEX_VEST = re.compile(r"^(?P<semestre>[12])sem(?P<ano>\d{4})\.csv$", re.IGNORECASE)


def normalizar_texto(valor: object) -> str:
    if pd.isna(valor):
        return ""
    texto = str(valor)
    texto = unicodedata.normalize("NFKC", texto)
    return " ".join(texto.strip().split())


def identificar_metadados(arquivo: Path, tipo_base: str) -> tuple[int, int]:
    regex = REGEX_ALUNOS if tipo_base == "ALUNOS" else REGEX_VEST
    match = regex.match(arquivo.name)
    if not match:
        raise ValueError(f"Nome de arquivo fora do padrão esperado: {arquivo.name}")
    return int(match.group("ano")), int(match.group("semestre"))


def ler_csv_bruto(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, sep=";", encoding="latin1", index_col=False)
    colunas_validas = [col for col in df.columns if normalizar_texto(col) != ""]
    return df.loc[:, colunas_validas].copy()


def inventariar_pasta(diretorio: Path, tipo_base: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    arquivos_info: list[dict[str, object]] = []
    colunas_info: list[dict[str, object]] = []

    for caminho in sorted(diretorio.glob("*.csv")):
        ano, semestre = identificar_metadados(caminho, tipo_base)
        df = ler_csv_bruto(caminho)

        arquivos_info.append(
            {
                "arquivo": caminho.name,
                "tipo_base": tipo_base,
                "ano_referencia": ano,
                "semestre_referencia": semestre,
                "quantidade_linhas": len(df),
                "quantidade_colunas": len(df.columns),
                "caminho_relativo": str(caminho.relative_to(RAIZ_PROJETO)),
            }
        )

        for ordem, coluna in enumerate(df.columns, start=1):
            colunas_info.append(
                {
                    "arquivo": caminho.name,
                    "tipo_base": tipo_base,
                    "ano_referencia": ano,
                    "semestre_referencia": semestre,
                    "ordem_coluna": ordem,
                    "nome_coluna": coluna,
                }
            )

    return arquivos_info, colunas_info


def montar_resumo_historico(arquivos_df: pd.DataFrame) -> pd.DataFrame:
    linhas: list[dict[str, object]] = []

    for tipo_base, grupo in arquivos_df.groupby("tipo_base", sort=True):
        anos = sorted(grupo["ano_referencia"].dropna().astype(int).unique().tolist())
        semestres = sorted(grupo["semestre_referencia"].dropna().astype(int).unique().tolist())
        linhas.append(
            {
                "tipo_base": tipo_base,
                "quantidade_bases": len(grupo),
                "anos_encontrados": ", ".join(str(ano) for ano in anos),
                "semestres_encontrados": ", ".join(str(sem) for sem in semestres),
                "total_linhas_historicas": int(grupo["quantidade_linhas"].sum()),
            }
        )

    linhas.append(
        {
            "tipo_base": "TOTAL_GERAL",
            "quantidade_bases": int(len(arquivos_df)),
            "anos_encontrados": ", ".join(
                str(ano) for ano in sorted(arquivos_df["ano_referencia"].dropna().astype(int).unique().tolist())
            ),
            "semestres_encontrados": ", ".join(
                str(sem) for sem in sorted(arquivos_df["semestre_referencia"].dropna().astype(int).unique().tolist())
            ),
            "total_linhas_historicas": int(arquivos_df["quantidade_linhas"].sum()),
        }
    )

    return pd.DataFrame(linhas)


def exportar_relatorio(
    arquivos_df: pd.DataFrame,
    colunas_alunos_df: pd.DataFrame,
    colunas_vest_df: pd.DataFrame,
    resumo_df: pd.DataFrame,
) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        arquivos_df.to_excel(writer, sheet_name="arquivos_encontrados", index=False)
        colunas_alunos_df.to_excel(writer, sheet_name="colunas_alunos", index=False)
        colunas_vest_df.to_excel(writer, sheet_name="colunas_vestibulinho", index=False)
        resumo_df.to_excel(writer, sheet_name="resumo_historico", index=False)


def main() -> None:
    arquivos_alunos, colunas_alunos = inventariar_pasta(DIR_ALUNOS, "ALUNOS")
    arquivos_vest, colunas_vest = inventariar_pasta(DIR_VESTIBULINHO, "VESTIBULINHO")

    arquivos_df = pd.DataFrame(arquivos_alunos + arquivos_vest).sort_values(
        ["tipo_base", "ano_referencia", "semestre_referencia", "arquivo"]
    )
    colunas_alunos_df = pd.DataFrame(colunas_alunos).sort_values(
        ["ano_referencia", "semestre_referencia", "arquivo", "ordem_coluna"]
    )
    colunas_vest_df = pd.DataFrame(colunas_vest).sort_values(
        ["ano_referencia", "semestre_referencia", "arquivo", "ordem_coluna"]
    )
    resumo_df = montar_resumo_historico(arquivos_df)

    exportar_relatorio(arquivos_df, colunas_alunos_df, colunas_vest_df, resumo_df)

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(arquivos_df[["arquivo", "tipo_base", "ano_referencia", "semestre_referencia", "quantidade_linhas", "quantidade_colunas"]].to_string(index=False))
    print(resumo_df.to_string(index=False))


if __name__ == "__main__":
    main()
