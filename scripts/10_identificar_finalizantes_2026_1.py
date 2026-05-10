from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))


ARQ_ALUNOS = RAIZ_PROJETO / "saida/curated/fato_alunos_turma_semestre.xlsx"
DIR_SAIDA = RAIZ_PROJETO / "saida/validacao"
ARQ_SAIDA = DIR_SAIDA / "FINALIZANTES_2026_1.xlsx"


def normalizar_tipo(valor: object) -> str:
    if pd.isna(valor):
        return ""
    return " ".join(str(valor).strip().upper().split())


def inferir_duracao_cursos(df: pd.DataFrame) -> pd.DataFrame:
    modular = df[df["tipo_etapa"].map(normalizar_tipo) == "MODULAR"].copy()
    if modular.empty:
        return pd.DataFrame(columns=["curso_canonico", "tipo_ensino", "duracao_curso_inferida"])

    duracao = (
        modular.groupby(["curso_canonico", "tipo_ensino"], dropna=False)["ordem_etapa"]
        .max()
        .reset_index(name="duracao_curso_inferida")
    )
    duracao["duracao_curso_inferida"] = pd.to_numeric(
        duracao["duracao_curso_inferida"], errors="coerce"
    ).astype("Int64")
    return duracao


def determinar_etapa_esperada(tipo_etapa: str, duracao: object) -> str:
    tipo = normalizar_tipo(tipo_etapa)
    if tipo == "ANUAL":
        return "3ª Série"
    if tipo == "MODULAR" and pd.notna(duracao):
        return f"{int(duracao)}º Módulo"
    return "REVISAR"


def marcar_finalizantes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    duracao = inferir_duracao_cursos(df)
    df = df.merge(
        duracao,
        on=["curso_canonico", "tipo_ensino"],
        how="left",
    )

    tipo_etapa_norm = df["tipo_etapa"].map(normalizar_tipo)
    ordem = pd.to_numeric(df["ordem_etapa"], errors="coerce")

    df["duracao_curso_inferida"] = df["duracao_curso_inferida"].where(
        tipo_etapa_norm == "MODULAR",
        3,
    )
    df["duracao_curso_inferida"] = df["duracao_curso_inferida"].astype("Int64")
    df["etapa_finalizante_esperada"] = df.apply(
        lambda linha: determinar_etapa_esperada(
            linha["tipo_etapa"], linha["duracao_curso_inferida"]
        ),
        axis=1,
    )

    flag_anual_finalizante = (tipo_etapa_norm == "ANUAL") & (ordem == 3)
    flag_modular_finalizante = (
        (tipo_etapa_norm == "MODULAR")
        & df["duracao_curso_inferida"].notna()
        & (ordem == pd.to_numeric(df["duracao_curso_inferida"], errors="coerce"))
    )

    df["flag_finalizante"] = "NAO"
    df.loc[flag_anual_finalizante | flag_modular_finalizante, "flag_finalizante"] = "SIM"
    return df


def montar_resumo(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quantidade_total_linhas": len(df),
                "quantidade_finalizantes": int((df["flag_finalizante"] == "SIM").sum()),
            }
        ]
    )


def montar_finalizantes_por_tipo_etapa(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df[df["flag_finalizante"] == "SIM"]
        .groupby(["tipo_etapa"], dropna=False)
        .size()
        .reset_index(name="quantidade")
        .sort_values("quantidade", ascending=False)
    )


def montar_finalizantes_por_curso(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df[df["flag_finalizante"] == "SIM"]
        .groupby(["curso_canonico", "tipo_ensino", "tipo_etapa"], dropna=False)
        .size()
        .reset_index(name="quantidade")
        .sort_values("quantidade", ascending=False)
    )


def montar_classificacao_cursos(df: pd.DataFrame) -> pd.DataFrame:
    cursos = (
        df[["curso_canonico", "tipo_ensino", "tipo_etapa", "duracao_curso_inferida", "etapa_finalizante_esperada"]]
        .drop_duplicates()
        .copy()
    )
    cursos["grupo_classificacao"] = cursos.apply(
        lambda linha: (
            "ANUAL"
            if normalizar_tipo(linha["tipo_etapa"]) == "ANUAL"
            else f"{int(linha['duracao_curso_inferida'])} MODULOS"
            if pd.notna(linha["duracao_curso_inferida"])
            else "REVISAR"
        ),
        axis=1,
    )
    return cursos.sort_values(["grupo_classificacao", "curso_canonico", "tipo_ensino"])


def montar_exemplos(df: pd.DataFrame) -> pd.DataFrame:
    base = df.copy()
    base["grupo_exemplo"] = base.apply(
        lambda linha: (
            "ANUAL"
            if normalizar_tipo(linha["tipo_etapa"]) == "ANUAL"
            else f"{int(linha['duracao_curso_inferida'])} MODULOS"
            if pd.notna(linha["duracao_curso_inferida"])
            else "REVISAR"
        ),
        axis=1,
    )

    exemplos = []
    for grupo in ["ANUAL", "2 MODULOS", "3 MODULOS", "4 MODULOS"]:
        subset = base[base["grupo_exemplo"] == grupo].head(10).copy()
        if not subset.empty:
            exemplos.append(subset)

    if not exemplos:
        return pd.DataFrame()

    return pd.concat(exemplos, ignore_index=True)[
        [
            "grupo_exemplo",
            "curso_canonico",
            "tipo_ensino",
            "tipo_etapa",
            "ordem_etapa",
            "turma_raw",
            "duracao_curso_inferida",
            "etapa_finalizante_esperada",
            "flag_finalizante",
            "codigo_unidade_canonico",
            "nome_unidade_canonico",
            "periodo_canonico",
            "numero_turma",
            "total_alunos",
        ]
    ]


def exportar(relatorio: dict[str, pd.DataFrame]) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        for aba, tabela in relatorio.items():
            tabela.to_excel(writer, sheet_name=aba, index=False)


def main() -> None:
    df = pd.read_excel(ARQ_ALUNOS)
    df_finalizantes = marcar_finalizantes(df)

    relatorio = {
        "resumo": montar_resumo(df_finalizantes),
        "finalizantes_detalhe": df_finalizantes,
        "finalizantes_por_tipo": montar_finalizantes_por_tipo_etapa(df_finalizantes),
        "finalizantes_por_curso": montar_finalizantes_por_curso(df_finalizantes),
        "classificacao_cursos": montar_classificacao_cursos(df_finalizantes),
        "exemplos": montar_exemplos(df_finalizantes),
    }
    exportar(relatorio)

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(relatorio["resumo"].to_string(index=False))


if __name__ == "__main__":
    main()
