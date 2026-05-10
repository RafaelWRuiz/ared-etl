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
DIR_SAIDA = RAIZ_PROJETO / "saida/validacao"
ARQ_SAIDA = DIR_SAIDA / "VALIDACAO_COORTES_ENTRADA.xlsx"


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


def carregar_fatos() -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_excel(ARQ_VEST), pd.read_excel(ARQ_ALUNOS)


def preparar_chave_entrada(df: pd.DataFrame, mapa: dict[str, str], origem: str) -> pd.DataFrame:
    base = df.copy()
    base["codigo_unidade_canonico_chave"] = base[mapa["codigo_unidade_canonico"]].map(normalizar_texto)
    base["curso_canonico_chave"] = base[mapa["curso_canonico"]].map(normalizar_texto)
    base["periodo_canonico_chave"] = base[mapa["periodo_canonico"]].map(normalizar_texto)
    base["tipo_ensino_chave"] = base[mapa["tipo_ensino"]].map(normalizar_texto)
    base["tipo_local_oferta_chave"] = base[mapa["tipo_local_oferta"]].map(normalizar_texto)
    base["chave_entrada"] = (
        base["codigo_unidade_canonico_chave"]
        + "|"
        + base["curso_canonico_chave"]
        + "|"
        + base["periodo_canonico_chave"]
        + "|"
        + base["tipo_ensino_chave"]
        + "|"
        + base["tipo_local_oferta_chave"]
    )
    base["origem_base"] = origem
    return base


def extrair_conjuntos(
    vest: pd.DataFrame,
    alunos: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mapa_vest = {
        "codigo_unidade_canonico": resolver_coluna(vest, "codigo_unidade_canonico"),
        "curso_canonico": resolver_coluna(vest, "curso_canonico"),
        "periodo_canonico": resolver_coluna(vest, "periodo_canonico"),
        "tipo_ensino": resolver_coluna(vest, "tipo_ensino"),
        "tipo_local_oferta": resolver_coluna(vest, "tipo_local_oferta"),
        "curso_raw": resolver_coluna(vest, "curso_raw"),
        "codigo_unidade_raw": resolver_coluna(vest, "codigo_unidade_raw"),
        "nome_unidade_raw": resolver_coluna(vest, "nome_unidade_raw"),
    }
    mapa_alunos = {
        "codigo_unidade_canonico": resolver_coluna(alunos, "codigo_unidade_canonico"),
        "curso_canonico": resolver_coluna(alunos, "curso_canonico"),
        "periodo_canonico": resolver_coluna(alunos, "periodo_canonico"),
        "tipo_ensino": resolver_coluna(alunos, "tipo_ensino"),
        "tipo_local_oferta": resolver_coluna(alunos, "tipo_local_oferta"),
        "turma_raw": resolver_coluna(alunos, "turma_raw"),
        "numero_turma": resolver_coluna(alunos, "numero_turma"),
        "flag_entrada": resolver_coluna(alunos, "flag_entrada"),
    }

    vest_keys = preparar_chave_entrada(vest, mapa_vest, "VESTIBULINHO")
    alunos_entrada = alunos[alunos[mapa_alunos["flag_entrada"]].map(normalizar_texto) == "SIM"].copy()
    alunos_keys = preparar_chave_entrada(alunos_entrada, mapa_alunos, "ALUNOS")

    return vest_keys, alunos_keys


def montar_matches(vest_keys: pd.DataFrame, alunos_keys: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "chave_entrada",
        "codigo_unidade_canonico_chave",
        "curso_canonico_chave",
        "periodo_canonico_chave",
        "tipo_ensino_chave",
        "tipo_local_oferta_chave",
    ]
    return (
        vest_keys[cols]
        .drop_duplicates()
        .merge(alunos_keys[cols].drop_duplicates(), on=cols, how="inner")
        .sort_values(cols)
        .reset_index(drop=True)
    )


def montar_apenas_vestibulinho(vest_keys: pd.DataFrame, alunos_keys: pd.DataFrame) -> pd.DataFrame:
    chaves_alunos = set(alunos_keys["chave_entrada"].unique())
    return vest_keys[~vest_keys["chave_entrada"].isin(chaves_alunos)].copy()


def montar_apenas_alunos(vest_keys: pd.DataFrame, alunos_keys: pd.DataFrame) -> pd.DataFrame:
    chaves_vest = set(vest_keys["chave_entrada"].unique())
    return alunos_keys[~alunos_keys["chave_entrada"].isin(chaves_vest)].copy()


def montar_divergencias_curso_raw(
    vest_keys: pd.DataFrame,
    alunos_keys: pd.DataFrame,
) -> pd.DataFrame:
    cols_analise = [
        "codigo_unidade_canonico_chave",
        "curso_canonico_chave",
        "periodo_canonico_chave",
        "tipo_ensino_chave",
    ]
    vest_agg = (
        vest_keys.groupby(cols_analise)["curso_raw"]
        .agg(lambda valores: " | ".join(sorted({normalizar_texto(v) for v in valores})))
        .reset_index(name="curso_raw_vestibulinho")
    )
    alunos_agg = (
        alunos_keys.groupby(cols_analise)["curso_canonico"]
        .agg(lambda valores: " | ".join(sorted({normalizar_texto(v) for v in valores})))
        .reset_index(name="curso_referencia_alunos")
    )
    merged = vest_agg.merge(alunos_agg, on=cols_analise, how="inner")
    return merged[merged["curso_raw_vestibulinho"] != merged["curso_referencia_alunos"]].copy()


def montar_divergencias_tipo_local(
    vest_keys: pd.DataFrame,
    alunos_keys: pd.DataFrame,
) -> pd.DataFrame:
    cols_analise = [
        "codigo_unidade_canonico_chave",
        "curso_canonico_chave",
        "periodo_canonico_chave",
        "tipo_ensino_chave",
    ]
    vest_agg = (
        vest_keys.groupby(cols_analise)["tipo_local_oferta_chave"]
        .agg(lambda valores: " | ".join(sorted(set(valores))))
        .reset_index(name="tipo_local_vestibulinho")
    )
    alunos_agg = (
        alunos_keys.groupby(cols_analise)["tipo_local_oferta_chave"]
        .agg(lambda valores: " | ".join(sorted(set(valores))))
        .reset_index(name="tipo_local_alunos")
    )
    merged = vest_agg.merge(alunos_agg, on=cols_analise, how="inner")
    return merged[merged["tipo_local_vestibulinho"] != merged["tipo_local_alunos"]].copy()


def exportar_relatorio(
    resumo: pd.DataFrame,
    matches: pd.DataFrame,
    apenas_alunos: pd.DataFrame,
    apenas_vest: pd.DataFrame,
    divergencias_curso: pd.DataFrame,
    divergencias_tipo_local: pd.DataFrame,
) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        resumo.to_excel(writer, sheet_name="resumo", index=False)
        matches.to_excel(writer, sheet_name="matches", index=False)
        apenas_alunos.to_excel(writer, sheet_name="apenas_alunos", index=False)
        apenas_vest.to_excel(writer, sheet_name="apenas_vestibulinho", index=False)
        divergencias_curso.to_excel(writer, sheet_name="divergencias_curso_raw", index=False)
        divergencias_tipo_local.to_excel(writer, sheet_name="divergencias_tipo_local", index=False)


def main() -> None:
    vest, alunos = carregar_fatos()
    vest_keys, alunos_keys = extrair_conjuntos(vest, alunos)

    matches = montar_matches(vest_keys, alunos_keys)
    apenas_vest = montar_apenas_vestibulinho(vest_keys, alunos_keys)
    apenas_alunos = montar_apenas_alunos(vest_keys, alunos_keys)
    divergencias_curso = montar_divergencias_curso_raw(vest_keys, alunos_keys)
    divergencias_tipo_local = montar_divergencias_tipo_local(vest_keys, alunos_keys)

    resumo = pd.DataFrame(
        [
            {
                "total_ofertas_vestibulinho": len(vest_keys),
                "total_turmas_entrada_alunos": len(alunos_keys),
                "matches": len(matches),
                "apenas_alunos": len(apenas_alunos),
                "apenas_vestibulinho": len(apenas_vest),
                "divergencias_curso_raw": len(divergencias_curso),
                "divergencias_tipo_local_oferta": len(divergencias_tipo_local),
            }
        ]
    )

    exportar_relatorio(
        resumo=resumo,
        matches=matches,
        apenas_alunos=apenas_alunos,
        apenas_vest=apenas_vest,
        divergencias_curso=divergencias_curso,
        divergencias_tipo_local=divergencias_tipo_local,
    )

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    main()
