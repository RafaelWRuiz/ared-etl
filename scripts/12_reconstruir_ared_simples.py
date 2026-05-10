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


ARQ_FINALIZANTES = RAIZ_PROJETO / "saida/validacao/FINALIZANTES_2026_1.xlsx"
ARQ_DURACAO = RAIZ_PROJETO / "saida/validacao/DURACAO_CURSOS_HISTORICO.xlsx"
DIR_ALUNOS = RAIZ_PROJETO / "dados_brutos/alunos"
DIR_VESTIBULINHO = RAIZ_PROJETO / "dados_brutos/vestibulinho"

ARQ_REF_CURSOS = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_curso.xlsx"
ARQ_REF_UNIDADES = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_unidade.xlsx"
ARQ_REF_PERIODO = RAIZ_PROJETO / "dados_brutos/referencias/ref_periodo.xlsx"
ARQ_REF_ETAPA = RAIZ_PROJETO / "dados_brutos/referencias/ref_etapa_turma.xlsx"

DIR_SAIDA = RAIZ_PROJETO / "saida/ared"
ARQ_SAIDA = DIR_SAIDA / "ARED_2026_1_SIMPLIFICADA.xlsx"

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


def identificar_competencia(arquivo: Path, tipo_base: str) -> tuple[int, int]:
    regex = REGEX_ALUNOS if tipo_base == "ALUNOS" else REGEX_VEST
    match = regex.match(arquivo.name)
    if not match:
        raise ValueError(f"Nome de arquivo fora do padrão esperado: {arquivo.name}")
    return int(match.group("ano")), int(match.group("semestre"))


def carregar_referencias() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_excel(ARQ_REF_CURSOS, sheet_name="ref_mapeamento_curso"),
        pd.read_excel(ARQ_REF_UNIDADES, sheet_name="ref_mapeamento_unidade"),
        pd.read_excel(ARQ_REF_PERIODO, sheet_name="ref_periodo"),
        pd.read_excel(ARQ_REF_ETAPA, sheet_name="ref_etapa_turma"),
    )


def consolidar_historico_alunos(
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
    ref_etapa: pd.DataFrame,
) -> pd.DataFrame:
    partes: list[pd.DataFrame] = []
    for caminho in sorted(DIR_ALUNOS.glob("*.csv")):
        ano, semestre = identificar_competencia(caminho, "ALUNOS")
        df = carregar_csv(caminho)

        col_curso = resolver_coluna(df, "Habilitação/Curso")
        col_codigo_unidade = resolver_coluna(df, "Código da Unidade")
        col_nome_unidade = resolver_coluna(df, "Unidades do CEETEPS")
        col_periodo = resolver_coluna(df, "Período")
        col_turma = resolver_coluna(df, "Turma")
        col_tipo_ensino = resolver_coluna(df, "Tipo de Ensino")
        col_total_alunos = resolver_coluna(df, "Total de Alunos")

        cursos = df[col_curso].map(lambda valor: normalizar_curso(valor, ref_cursos))
        unidades = df.apply(
            lambda linha: normalizar_unidade(
                codigo_raw=linha[col_codigo_unidade],
                nome_raw=linha[col_nome_unidade],
                ref_unidades_df=ref_unidades,
            ),
            axis=1,
        )
        periodos = df[col_periodo].map(lambda valor: normalizar_periodo(valor, ref_periodo))
        etapas = df[col_turma].map(lambda valor: normalizar_etapa(valor, ref_etapa))

        partes.append(
            pd.DataFrame(
                {
                    "competencia": f"{ano}.{semestre}",
                    "curso_canonico": cursos.map(lambda valor: valor["curso_canonico"]),
                    "codigo_unidade_canonico": unidades.map(lambda valor: valor["codigo_unidade_canonico"]),
                    "nome_unidade_canonico": unidades.map(lambda valor: valor["nome_unidade_canonico"]),
                    "periodo_canonico": periodos.map(lambda valor: valor["periodo_canonico"]),
                    "tipo_ensino": df[col_tipo_ensino].map(normalizar_texto),
                    "tipo_etapa": etapas.map(lambda valor: valor["tipo_etapa"]),
                    "ordem_etapa": etapas.map(lambda valor: valor["ordem_etapa"]),
                    "turma_raw": df[col_turma],
                    "total_alunos": pd.to_numeric(df[col_total_alunos], errors="coerce"),
                }
            )
        )
    return pd.concat(partes, ignore_index=True)


def consolidar_historico_vestibulinho(
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
) -> pd.DataFrame:
    partes: list[pd.DataFrame] = []
    for caminho in sorted(DIR_VESTIBULINHO.glob("*.csv")):
        ano, semestre = identificar_competencia(caminho, "VESTIBULINHO")
        df = carregar_csv(caminho)

        col_curso = resolver_coluna(df, "Curso/Habilitação")
        col_codigo = resolver_coluna(df, "Código")
        col_nome_unidade = resolver_coluna(df, "Unidades do CEETEPS")
        col_periodo = resolver_coluna(df, "Período")
        col_tipo_ensino = resolver_coluna(df, "Tipo de Ensino")
        col_vagas = resolver_coluna(df, "Vagas")
        col_inscritos = resolver_coluna(df, "Inscritos")
        col_demanda = resolver_coluna(df, "Demanda")

        cursos = df[col_curso].map(lambda valor: normalizar_curso(valor, ref_cursos))
        unidades = df.apply(
            lambda linha: normalizar_unidade(
                codigo_raw=linha[col_codigo],
                nome_raw=linha[col_nome_unidade],
                ref_unidades_df=ref_unidades,
            ),
            axis=1,
        )
        periodos = df[col_periodo].map(lambda valor: normalizar_periodo(valor, ref_periodo))

        partes.append(
            pd.DataFrame(
                {
                    "competencia": f"{ano}.{semestre}",
                    "curso_canonico": cursos.map(lambda valor: valor["curso_canonico"]),
                    "codigo_unidade_canonico": unidades.map(lambda valor: valor["codigo_unidade_canonico"]),
                    "nome_unidade_canonico": unidades.map(lambda valor: valor["nome_unidade_canonico"]),
                    "periodo_canonico": periodos.map(lambda valor: valor["periodo_canonico"]),
                    "tipo_ensino": df[col_tipo_ensino].map(normalizar_texto),
                    "vagas": pd.to_numeric(df[col_vagas], errors="coerce"),
                    "inscritos": pd.to_numeric(df[col_inscritos], errors="coerce"),
                    "demanda": pd.to_numeric(df[col_demanda], errors="coerce"),
                }
            )
        )
    return pd.concat(partes, ignore_index=True)


def montar_lookup_alunos(historico: pd.DataFrame) -> dict[tuple[str, str, str, str, str, str, int], pd.DataFrame]:
    lookup: dict[tuple[str, str, str, str, str, str, int], pd.DataFrame] = {}
    base = historico.copy()
    base["ordem_etapa_int"] = pd.to_numeric(base["ordem_etapa"], errors="coerce").fillna(-1).astype(int)
    for chave, grupo in base.groupby(
        [
            "competencia",
            "codigo_unidade_canonico",
            "curso_canonico",
            "periodo_canonico",
            "tipo_ensino",
            "tipo_etapa",
            "ordem_etapa_int",
        ],
        dropna=False,
        sort=False,
    ):
        lookup[tuple(normalizar_texto(v) if not isinstance(v, int) else v for v in chave)] = grupo.copy()
    return lookup


def montar_lookup_vest(historico: pd.DataFrame) -> dict[tuple[str, str, str, str, str], pd.DataFrame]:
    lookup: dict[tuple[str, str, str, str, str], pd.DataFrame] = {}
    for chave, grupo in historico.groupby(
        ["competencia", "codigo_unidade_canonico", "curso_canonico", "periodo_canonico", "tipo_ensino"],
        dropna=False,
        sort=False,
    ):
        lookup[tuple(normalizar_texto(v) for v in chave)] = grupo.copy()
    return lookup


def calcular_percentual(op: object, vagas: object) -> object:
    op_num = pd.to_numeric(op, errors="coerce")
    vagas_num = pd.to_numeric(vagas, errors="coerce")
    if pd.isna(op_num) or pd.isna(vagas_num) or vagas_num == 0:
        return pd.NA
    return (float(op_num) - float(vagas_num)) / float(vagas_num)


def selecionar_competencias(tipo_etapa: str, duracao: int) -> list[tuple[int, str]]:
    tipo = normalizar_texto(tipo_etapa).upper()
    if tipo == "ANUAL":
        return [(1, "2024.1"), (2, "2025.1"), (3, "2026.1")]
    if duracao == 2:
        return [(1, "2025.2"), (2, "2026.1")]
    if duracao == 3:
        return [(1, "2025.1"), (2, "2025.2"), (3, "2026.1")]
    if duracao == 4:
        return [(1, "2024.2"), (2, "2025.1"), (3, "2025.2"), (4, "2026.1")]
    return []


def buscar_op(
    lookup_alunos: dict[tuple[str, str, str, str, str, str, int], pd.DataFrame],
    linha: pd.Series,
    competencia: str,
    ordem: int,
) -> tuple[object, str]:
    chave = (
        normalizar_texto(competencia),
        normalizar_texto(linha["codigo_unidade_canonico"]),
        normalizar_texto(linha["curso_canonico"]),
        normalizar_texto(linha["periodo_canonico"]),
        normalizar_texto(linha["tipo_ensino"]),
        normalizar_texto(linha["tipo_etapa"]),
        int(ordem),
    )
    candidatos = lookup_alunos.get(chave, pd.DataFrame())
    if len(candidatos) == 1:
        return candidatos.iloc[0]["total_alunos"], "OK"
    if len(candidatos) == 0:
        return pd.NA, f"SEM_ETAPA_{ordem}"
    return pd.NA, f"MULTIPLO_ETAPA_{ordem}"


def buscar_vestib(
    lookup_vest: dict[tuple[str, str, str, str, str], pd.DataFrame],
    linha: pd.Series,
    competencia_entrada: str,
) -> tuple[object, object, object, str]:
    chave = (
        normalizar_texto(competencia_entrada),
        normalizar_texto(linha["codigo_unidade_canonico"]),
        normalizar_texto(linha["curso_canonico"]),
        normalizar_texto(linha["periodo_canonico"]),
        normalizar_texto(linha["tipo_ensino"]),
    )
    candidatos = lookup_vest.get(chave, pd.DataFrame())
    if len(candidatos) == 1:
        item = candidatos.iloc[0]
        return item["inscritos"], item["vagas"], item["demanda"], "OK"
    if len(candidatos) == 0:
        return pd.NA, pd.NA, pd.NA, "SEM_VESTIBULINHO"
    return pd.NA, pd.NA, pd.NA, "MULTIPLO_VESTIBULINHO"


def reconstruir_linha(
    linha: pd.Series,
    duracao_lookup: pd.DataFrame,
    lookup_alunos: dict[tuple[str, str, str, str, str, str, int], pd.DataFrame],
    lookup_vest: dict[tuple[str, str, str, str, str], pd.DataFrame],
) -> dict[str, object]:
    duracao_match = duracao_lookup[
        (duracao_lookup["curso_canonico"].map(normalizar_texto) == normalizar_texto(linha["curso_canonico"]))
        & (duracao_lookup["tipo_ensino"].map(normalizar_texto) == normalizar_texto(linha["tipo_ensino"]))
    ]
    duracao = (
        int(duracao_match.iloc[0]["duracao_inferida"])
        if not duracao_match.empty and pd.notna(duracao_match.iloc[0]["duracao_inferida"])
        else int(linha["duracao_curso_inferida"])
    )

    competencias = selecionar_competencias(linha["tipo_etapa"], duracao)
    competencia_entrada = competencias[0][1] if competencias else ""
    inscritos, vagas, demanda, status_vest = buscar_vestib(lookup_vest, linha, competencia_entrada)

    ops: dict[int, object] = {1: pd.NA, 2: pd.NA, 3: pd.NA, 4: pd.NA}
    status = []
    if status_vest != "OK":
        status.append(status_vest)

    for ordem, competencia in competencias:
        valor, status_etapa = buscar_op(lookup_alunos, linha, competencia, ordem)
        ops[ordem] = valor
        if status_etapa != "OK":
            status.append(status_etapa)

    if not status:
        status.append("OK")

    ultimo_op = pd.NA
    for ordem in [4, 3, 2, 1]:
        if pd.notna(ops[ordem]):
            ultimo_op = ops[ordem]
            break

    return {
        "codigo_unidade": linha["codigo_unidade_canonico"],
        "unidade": linha["nome_unidade_canonico"],
        "curso": linha["curso_canonico"],
        "periodo": linha["periodo_canonico"],
        "tipo_ensino": linha["tipo_ensino"],
        "duracao": duracao,
        "competencia_entrada": competencia_entrada,
        "inscritos": inscritos,
        "vagas": vagas,
        "demanda": demanda,
        "op1": ops[1],
        "perc_op1": calcular_percentual(ops[1], vagas),
        "op2": ops[2],
        "perc_op2": calcular_percentual(ops[2], vagas),
        "op3": ops[3],
        "perc_op3": calcular_percentual(ops[3], vagas),
        "op4": ops[4],
        "perc_op4": calcular_percentual(ops[4], vagas),
        "acumulado": ultimo_op,
        "status_match": " | ".join(status),
    }


def montar_resumo(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "linhas_geradas": len(df),
                "status_ok": int((df["status_match"] == "OK").sum()),
                "status_com_problema": int((df["status_match"] != "OK").sum()),
            }
        ]
    )


def exportar(ared: pd.DataFrame, resumo: pd.DataFrame) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        ared.to_excel(writer, sheet_name="ared_2026_1", index=False)
        resumo.to_excel(writer, sheet_name="resumo", index=False)


def main() -> None:
    ref_cursos, ref_unidades, ref_periodo, ref_etapa = carregar_referencias()
    finalizantes = pd.read_excel(ARQ_FINALIZANTES, sheet_name="finalizantes_detalhe")
    finalizantes = finalizantes[finalizantes["flag_finalizante"].map(normalizar_texto) == "SIM"].copy()
    duracao = pd.read_excel(ARQ_DURACAO, sheet_name="duracao_cursos")

    historico_alunos = consolidar_historico_alunos(ref_cursos, ref_unidades, ref_periodo, ref_etapa)
    historico_vest = consolidar_historico_vestibulinho(ref_cursos, ref_unidades, ref_periodo)
    lookup_alunos = montar_lookup_alunos(historico_alunos)
    lookup_vest = montar_lookup_vest(historico_vest)

    ared = pd.DataFrame(
        [
            reconstruir_linha(linha, duracao, lookup_alunos, lookup_vest)
            for _, linha in finalizantes.iterrows()
        ]
    )
    resumo = montar_resumo(ared)
    exportar(ared, resumo)

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(resumo.to_string(index=False))


if __name__ == "__main__":
    main()
