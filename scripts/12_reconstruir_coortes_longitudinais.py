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

DIR_SAIDA = RAIZ_PROJETO / "saida/validacao"
ARQ_SAIDA = DIR_SAIDA / "COORTES_LONGITUDINAIS_2026_1.xlsx"

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
    ref_cursos = pd.read_excel(ARQ_REF_CURSOS, sheet_name="ref_mapeamento_curso")
    ref_unidades = pd.read_excel(ARQ_REF_UNIDADES, sheet_name="ref_mapeamento_unidade")
    ref_periodo = pd.read_excel(ARQ_REF_PERIODO, sheet_name="ref_periodo")
    ref_etapa = pd.read_excel(ARQ_REF_ETAPA, sheet_name="ref_etapa_turma")
    return ref_cursos, ref_unidades, ref_periodo, ref_etapa


def value_to_bool_text(valor: bool) -> str:
    return "SIM" if valor else "NAO"


def consolidar_historico_alunos(
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
    ref_etapa: pd.DataFrame,
) -> pd.DataFrame:
    partes: list[pd.DataFrame] = []
    for caminho in sorted(DIR_ALUNOS.glob("*.csv")):
        ano_referencia, semestre_referencia = identificar_competencia(caminho, "ALUNOS")
        df = carregar_csv(caminho)

        col_curso = resolver_coluna(df, "Habilitação/Curso")
        col_codigo_unidade = resolver_coluna(df, "Código da Unidade")
        col_nome_unidade = resolver_coluna(df, "Unidades do CEETEPS")
        col_periodo = resolver_coluna(df, "Período")
        col_turma = resolver_coluna(df, "Turma")
        col_tipo_ensino = resolver_coluna(df, "Tipo de Ensino")
        col_numero_turma = resolver_coluna(df, "Número da Turma")
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

        parte = pd.DataFrame(
            {
                "periodo_referencia": f"{ano_referencia}.{semestre_referencia}",
                "ano_referencia": ano_referencia,
                "semestre_referencia": semestre_referencia,
                "arquivo_origem": caminho.name,
                "curso_raw": df[col_curso],
                "curso_canonico": cursos.map(lambda valor: valor["curso_canonico"]),
                "codigo_unidade_canonico": unidades.map(lambda valor: valor["codigo_unidade_canonico"]),
                "nome_unidade_canonico": unidades.map(lambda valor: valor["nome_unidade_canonico"]),
                "tipo_local_oferta": unidades.map(lambda valor: valor["tipo_local_oferta"]),
                "periodo_canonico": periodos.map(lambda valor: valor["periodo_canonico"]),
                "tipo_ensino": df[col_tipo_ensino].map(normalizar_texto),
                "turma_raw": df[col_turma],
                "tipo_etapa": etapas.map(lambda valor: valor["tipo_etapa"]),
                "ordem_etapa": etapas.map(lambda valor: valor["ordem_etapa"]),
                "numero_turma": df[col_numero_turma].map(normalizar_texto),
                "total_alunos": pd.to_numeric(df[col_total_alunos], errors="coerce"),
                "flag_etapa_nao_mapeada": etapas.map(lambda valor: value_to_bool_text(valor["flag_nao_mapeado"])),
            }
        )
        partes.append(parte)

    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def consolidar_historico_vestibulinho(
    ref_cursos: pd.DataFrame,
    ref_unidades: pd.DataFrame,
    ref_periodo: pd.DataFrame,
) -> pd.DataFrame:
    partes: list[pd.DataFrame] = []
    for caminho in sorted(DIR_VESTIBULINHO.glob("*.csv")):
        ano_referencia, semestre_referencia = identificar_competencia(caminho, "VESTIBULINHO")
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

        parte = pd.DataFrame(
            {
                "periodo_referencia": f"{ano_referencia}.{semestre_referencia}",
                "ano_referencia": ano_referencia,
                "semestre_referencia": semestre_referencia,
                "arquivo_origem": caminho.name,
                "curso_raw": df[col_curso],
                "curso_canonico": cursos.map(lambda valor: valor["curso_canonico"]),
                "codigo_unidade_canonico": unidades.map(lambda valor: valor["codigo_unidade_canonico"]),
                "nome_unidade_canonico": unidades.map(lambda valor: valor["nome_unidade_canonico"]),
                "tipo_local_oferta": unidades.map(lambda valor: valor["tipo_local_oferta"]),
                "periodo_canonico": periodos.map(lambda valor: valor["periodo_canonico"]),
                "tipo_ensino": df[col_tipo_ensino].map(normalizar_texto),
                "vagas": pd.to_numeric(df[col_vagas], errors="coerce"),
                "inscritos": pd.to_numeric(df[col_inscritos], errors="coerce"),
                "demanda": pd.to_numeric(df[col_demanda], errors="coerce"),
            }
        )
        partes.append(parte)

    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def montar_lookup_alunos(historico: pd.DataFrame) -> dict[tuple[str, str, str, str, str, str, int], pd.DataFrame]:
    lookup: dict[tuple[str, str, str, str, str, str, int], pd.DataFrame] = {}
    base = historico.copy()
    base["ordem_etapa_int"] = pd.to_numeric(base["ordem_etapa"], errors="coerce").fillna(-1).astype(int)
    for chave, grupo in base.groupby(
        [
            "periodo_referencia",
            "codigo_unidade_canonico",
            "curso_canonico",
            "periodo_canonico",
            "tipo_ensino",
            "tipo_local_oferta",
            "ordem_etapa_int",
        ],
        dropna=False,
        sort=False,
    ):
        chave_norm = (
            normalizar_texto(chave[0]),
            normalizar_texto(chave[1]),
            normalizar_texto(chave[2]),
            normalizar_texto(chave[3]),
            normalizar_texto(chave[4]),
            normalizar_texto(chave[5]),
            int(chave[6]),
        )
        lookup[chave_norm] = grupo.copy()
    return lookup


def montar_lookup_vestib(historico: pd.DataFrame) -> dict[tuple[str, str, str, str, str, str], pd.DataFrame]:
    lookup: dict[tuple[str, str, str, str, str, str], pd.DataFrame] = {}
    for chave, grupo in historico.groupby(
        [
            "periodo_referencia",
            "codigo_unidade_canonico",
            "curso_canonico",
            "periodo_canonico",
            "tipo_ensino",
            "tipo_local_oferta",
        ],
        dropna=False,
        sort=False,
    ):
        chave_norm = tuple(normalizar_texto(item) for item in chave)
        lookup[chave_norm] = grupo.copy()
    return lookup


def periodo_anterior(ano: int, semestre: int) -> tuple[int, int]:
    return (ano - 1, 2) if semestre == 1 else (ano, 1)


def retroceder_competencia(ano_final: int, semestre_final: int, passos: int, tipo_etapa: str) -> tuple[int, int]:
    tipo = normalizar_texto(tipo_etapa).upper()
    ano_atual, semestre_atual = ano_final, semestre_final

    if tipo == "ANUAL":
        return ano_final - passos, semestre_final

    for _ in range(passos):
        ano_atual, semestre_atual = periodo_anterior(ano_atual, semestre_atual)
    return ano_atual, semestre_atual


def montar_coorte_id(linha: pd.Series) -> str:
    return (
        f"{linha['ano_referencia']}.{linha['semestre_referencia']}"
        f"|{normalizar_texto(linha['codigo_unidade_canonico'])}"
        f"|{normalizar_texto(linha['curso_canonico'])}"
        f"|{normalizar_texto(linha['tipo_ensino'])}"
        f"|{normalizar_texto(linha['periodo_canonico'])}"
        f"|{normalizar_texto(linha['tipo_local_oferta'])}"
        f"|{normalizar_texto(linha['numero_turma'])}"
    )


def selecionar_candidatos_alunos(
    lookup: dict[tuple[str, str, str, str, str, str, int], pd.DataFrame],
    finalizante: pd.Series,
    periodo_referencia: str,
    ordem_etapa: int,
) -> pd.DataFrame:
    chave = (
        normalizar_texto(periodo_referencia),
        normalizar_texto(finalizante["codigo_unidade_canonico"]),
        normalizar_texto(finalizante["curso_canonico"]),
        normalizar_texto(finalizante["periodo_canonico"]),
        normalizar_texto(finalizante["tipo_ensino"]),
        normalizar_texto(finalizante["tipo_local_oferta"]),
        int(ordem_etapa),
    )
    return lookup.get(chave, pd.DataFrame()).copy()


def selecionar_candidatos_vestib(
    lookup: dict[tuple[str, str, str, str, str, str], pd.DataFrame],
    finalizante: pd.Series,
    periodo_referencia: str,
) -> pd.DataFrame:
    chave = (
        normalizar_texto(periodo_referencia),
        normalizar_texto(finalizante["codigo_unidade_canonico"]),
        normalizar_texto(finalizante["curso_canonico"]),
        normalizar_texto(finalizante["periodo_canonico"]),
        normalizar_texto(finalizante["tipo_ensino"]),
        normalizar_texto(finalizante["tipo_local_oferta"]),
    )
    return lookup.get(chave, pd.DataFrame()).copy()


def resumir_candidatos_alunos(candidatos: pd.DataFrame) -> dict[str, object]:
    qtd = len(candidatos)
    resumo = {
        "quantidade_candidatos": qtd,
        "status": "NAO_ENCONTRADO" if qtd == 0 else "UNICO" if qtd == 1 else "MULTIPLO",
        "numero_turma": "",
        "turma_raw": "",
        "total_alunos": pd.NA,
        "exemplo_candidatos": "",
    }
    if qtd == 1:
        linha = candidatos.iloc[0]
        resumo["numero_turma"] = normalizar_texto(linha["numero_turma"])
        resumo["turma_raw"] = normalizar_texto(linha["turma_raw"])
        resumo["total_alunos"] = linha["total_alunos"]
    if qtd > 0:
        resumo["exemplo_candidatos"] = " | ".join(
            (
                candidatos["numero_turma"].map(normalizar_texto)
                + " (" + candidatos["turma_raw"].map(normalizar_texto) + ")"
            ).head(5).tolist()
        )
    return resumo


def resumir_candidatos_vestib(candidatos: pd.DataFrame) -> dict[str, object]:
    qtd = len(candidatos)
    resumo = {
        "quantidade_candidatos": qtd,
        "status": "NAO_ENCONTRADO" if qtd == 0 else "UNICO" if qtd == 1 else "MULTIPLO",
        "vagas": pd.NA,
        "inscritos": pd.NA,
        "demanda": pd.NA,
        "exemplo_candidatos": "",
    }
    if qtd == 1:
        linha = candidatos.iloc[0]
        resumo["vagas"] = linha["vagas"]
        resumo["inscritos"] = linha["inscritos"]
        resumo["demanda"] = linha["demanda"]
    if qtd > 0:
        resumo["exemplo_candidatos"] = " | ".join(
            (
                candidatos["periodo_canonico"].map(normalizar_texto)
                + " | "
                + candidatos["tipo_local_oferta"].map(normalizar_texto)
                + " | "
                + candidatos["curso_raw"].map(normalizar_texto)
            ).head(5).tolist()
        )
    return resumo


def reconstruir_coorte(
    finalizante: pd.Series,
    lookup_alunos: dict[tuple[str, str, str, str, str, str, int], pd.DataFrame],
    lookup_vest: dict[tuple[str, str, str, str, str, str], pd.DataFrame],
    duracao_lookup: pd.DataFrame,
) -> dict[str, object]:
    curso = normalizar_texto(finalizante["curso_canonico"])
    tipo_ensino = normalizar_texto(finalizante["tipo_ensino"])
    duracao_match = duracao_lookup[
        (duracao_lookup["curso_canonico"].map(normalizar_texto) == curso)
        & (duracao_lookup["tipo_ensino"].map(normalizar_texto) == tipo_ensino)
    ]
    duracao_inferida = (
        int(duracao_match.iloc[0]["duracao_inferida"])
        if not duracao_match.empty and pd.notna(duracao_match.iloc[0]["duracao_inferida"])
        else int(finalizante["duracao_curso_inferida"])
    )

    tipo_etapa = normalizar_texto(finalizante["tipo_etapa"]).upper()
    ano_final = int(finalizante["ano_referencia"])
    semestre_final = int(finalizante["semestre_referencia"])
    ordem_final = int(finalizante["ordem_etapa"])

    resultado: dict[str, object] = {
        "coorte_id": montar_coorte_id(finalizante),
        "curso_canonico": finalizante["curso_canonico"],
        "tipo_ensino": finalizante["tipo_ensino"],
        "tipo_etapa": finalizante["tipo_etapa"],
        "duracao_inferida": duracao_inferida,
        "codigo_unidade_canonico": finalizante["codigo_unidade_canonico"],
        "nome_unidade_canonico": finalizante["nome_unidade_canonico"],
        "periodo_canonico": finalizante["periodo_canonico"],
        "tipo_local_oferta": finalizante["tipo_local_oferta"],
        "numero_turma_finalizante": finalizante["numero_turma"],
        "turma_raw_finalizante": finalizante["turma_raw"],
        "total_alunos_finalizante": finalizante["total_alunos"],
        "competencia_finalizacao": f"{ano_final}.{semestre_final}",
    }

    etapas_previstas = max(duracao_inferida, ordem_final)
    status_etapas: list[str] = []
    multiplos = False

    for ordem in range(1, 5):
        prefixo = f"etapa_{ordem}"
        if ordem > etapas_previstas:
            resultado[f"{prefixo}_competencia"] = ""
            resultado[f"{prefixo}_ordem_esperada"] = pd.NA
            resultado[f"{prefixo}_status"] = "NAO_APLICAVEL"
            resultado[f"{prefixo}_qtd_candidatos"] = 0
            resultado[f"{prefixo}_numero_turma"] = ""
            resultado[f"{prefixo}_turma_raw"] = ""
            resultado[f"{prefixo}_total_alunos"] = pd.NA
            resultado[f"{prefixo}_exemplo_candidatos"] = ""
            continue

        passos = etapas_previstas - ordem
        ano_etapa, semestre_etapa = retroceder_competencia(ano_final, semestre_final, passos, tipo_etapa)
        competencia = f"{ano_etapa}.{semestre_etapa}"
        candidatos = selecionar_candidatos_alunos(lookup_alunos, finalizante, competencia, ordem)
        resumo = resumir_candidatos_alunos(candidatos)

        resultado[f"{prefixo}_competencia"] = competencia
        resultado[f"{prefixo}_ordem_esperada"] = ordem
        resultado[f"{prefixo}_status"] = resumo["status"]
        resultado[f"{prefixo}_qtd_candidatos"] = resumo["quantidade_candidatos"]
        resultado[f"{prefixo}_numero_turma"] = resumo["numero_turma"]
        resultado[f"{prefixo}_turma_raw"] = resumo["turma_raw"]
        resultado[f"{prefixo}_total_alunos"] = resumo["total_alunos"]
        resultado[f"{prefixo}_exemplo_candidatos"] = resumo["exemplo_candidatos"]
        status_etapas.append(resumo["status"])
        if resumo["status"] == "MULTIPLO":
            multiplos = True

    competencia_entrada = resultado["etapa_1_competencia"]
    vest_candidatos = selecionar_candidatos_vestib(lookup_vest, finalizante, competencia_entrada)
    vest_resumo = resumir_candidatos_vestib(vest_candidatos)
    resultado["vestibulinho_entrada_competencia"] = competencia_entrada
    resultado["vestibulinho_entrada_status"] = vest_resumo["status"]
    resultado["vestibulinho_entrada_qtd_candidatos"] = vest_resumo["quantidade_candidatos"]
    resultado["vestibulinho_entrada_vagas"] = vest_resumo["vagas"]
    resultado["vestibulinho_entrada_inscritos"] = vest_resumo["inscritos"]
    resultado["vestibulinho_entrada_demanda"] = vest_resumo["demanda"]
    resultado["vestibulinho_entrada_exemplo_candidatos"] = vest_resumo["exemplo_candidatos"]
    if vest_resumo["status"] == "MULTIPLO":
        multiplos = True

    etapas_ativas = [status for status in status_etapas if status != "NAO_APLICAVEL"]
    completa = all(status == "UNICO" for status in etapas_ativas) and vest_resumo["status"] == "UNICO"
    resultado["flag_trajetoria_completa"] = "SIM" if completa else "NAO"
    resultado["flag_multiplos_candidatos"] = "SIM" if multiplos else "NAO"
    resultado["flag_sem_vestibulinho"] = "SIM" if vest_resumo["status"] == "NAO_ENCONTRADO" else "NAO"
    return resultado


def montar_resumo(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quantidade_coortes_reconstruidas": len(df),
                "quantidade_trajetoria_completa": int((df["flag_trajetoria_completa"] == "SIM").sum()),
                "quantidade_incompleta": int((df["flag_trajetoria_completa"] == "NAO").sum()),
                "quantidade_sem_vestibulinho": int((df["flag_sem_vestibulinho"] == "SIM").sum()),
                "quantidade_multiplos_candidatos": int((df["flag_multiplos_candidatos"] == "SIM").sum()),
            }
        ]
    )


def filtrar_exemplos(df: pd.DataFrame, classificacao: str) -> pd.DataFrame:
    return df[df["classificacao_duracao"] == classificacao].head(20).copy()


def exportar(relatorio: dict[str, pd.DataFrame]) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        for aba, tabela in relatorio.items():
            tabela.to_excel(writer, sheet_name=aba, index=False)


def main() -> None:
    ref_cursos, ref_unidades, ref_periodo, ref_etapa = carregar_referencias()
    finalizantes = pd.read_excel(ARQ_FINALIZANTES, sheet_name="finalizantes_detalhe")
    finalizantes = finalizantes[finalizantes["flag_finalizante"].map(normalizar_texto) == "SIM"].copy()
    duracao = pd.read_excel(ARQ_DURACAO, sheet_name="duracao_cursos")

    historico_alunos = consolidar_historico_alunos(ref_cursos, ref_unidades, ref_periodo, ref_etapa)
    historico_alunos = historico_alunos[historico_alunos["flag_etapa_nao_mapeada"] == "NAO"].copy()
    historico_vest = consolidar_historico_vestibulinho(ref_cursos, ref_unidades, ref_periodo)
    lookup_alunos = montar_lookup_alunos(historico_alunos)
    lookup_vest = montar_lookup_vestib(historico_vest)

    reconstruidas = pd.DataFrame(
        [reconstruir_coorte(linha, lookup_alunos, lookup_vest, duracao) for _, linha in finalizantes.iterrows()]
    )

    reconstruidas = reconstruidas.merge(
        duracao[["curso_canonico", "tipo_ensino", "classificacao"]].rename(columns={"classificacao": "classificacao_duracao"}),
        on=["curso_canonico", "tipo_ensino"],
        how="left",
    )

    relatorio = {
        "resumo": montar_resumo(reconstruidas),
        "coortes_reconstruidas": reconstruidas,
        "exemplos_anuais": filtrar_exemplos(reconstruidas, "ANUAL_3_SERIES"),
        "exemplos_modulares_2": filtrar_exemplos(reconstruidas, "MODULAR_2"),
        "exemplos_modulares_3": filtrar_exemplos(reconstruidas, "MODULAR_3"),
        "exemplos_modulares_4": filtrar_exemplos(reconstruidas, "MODULAR_4"),
        "casos_sem_vestibulinho": reconstruidas[reconstruidas["flag_sem_vestibulinho"] == "SIM"].copy(),
        "casos_multiplos_candidatos": reconstruidas[reconstruidas["flag_multiplos_candidatos"] == "SIM"].copy(),
    }
    exportar(relatorio)

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(relatorio["resumo"].to_string(index=False))


if __name__ == "__main__":
    main()
