from __future__ import annotations

from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from ared.normalizar import normalizar_curso, normalizar_etapa, normalizar_texto  # noqa: E402


DIR_ALUNOS = RAIZ_PROJETO / "dados_brutos/alunos"
ARQ_REF_CURSOS = RAIZ_PROJETO / "dados_brutos/referencias/ref_mapeamento_curso.xlsx"
ARQ_REF_ETAPA = RAIZ_PROJETO / "dados_brutos/referencias/ref_etapa_turma.xlsx"
DIR_SAIDA = RAIZ_PROJETO / "saida/validacao"
ARQ_SAIDA = DIR_SAIDA / "DURACAO_CURSOS_HISTORICO.xlsx"

REGEX_ALUNOS = re.compile(r"^totais_alunos_(?P<semestre>[12])sem(?P<ano>\d{4})\.csv$", re.IGNORECASE)


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


def identificar_competencia(arquivo: Path) -> tuple[int, int]:
    match = REGEX_ALUNOS.match(arquivo.name)
    if not match:
        raise ValueError(f"Nome de arquivo fora do padrão esperado: {arquivo.name}")
    return int(match.group("ano")), int(match.group("semestre"))


def carregar_referencias() -> tuple[pd.DataFrame, pd.DataFrame]:
    ref_cursos = pd.read_excel(ARQ_REF_CURSOS, sheet_name="ref_mapeamento_curso")
    ref_etapa = pd.read_excel(ARQ_REF_ETAPA, sheet_name="ref_etapa_turma")
    return ref_cursos, ref_etapa


def consolidar_historico_alunos(ref_cursos: pd.DataFrame, ref_etapa: pd.DataFrame) -> pd.DataFrame:
    partes: list[pd.DataFrame] = []
    for caminho in sorted(DIR_ALUNOS.glob("*.csv")):
        ano_referencia, semestre_referencia = identificar_competencia(caminho)
        df = carregar_csv(caminho)

        col_curso = resolver_coluna(df, "Habilitação/Curso")
        col_turma = resolver_coluna(df, "Turma")
        col_tipo_ensino = resolver_coluna(df, "Tipo de Ensino")

        cursos = df[col_curso].map(lambda valor: normalizar_curso(valor, ref_cursos))
        etapas = df[col_turma].map(lambda valor: normalizar_etapa(valor, ref_etapa))

        base = pd.DataFrame(
            {
                "arquivo_origem": caminho.name,
                "ano_referencia": ano_referencia,
                "semestre_referencia": semestre_referencia,
                "periodo_referencia": f"{ano_referencia}.{semestre_referencia}",
                "curso_raw": df[col_curso],
                "curso_canonico": cursos.map(lambda valor: valor["curso_canonico"]),
                "tipo_ensino": df[col_tipo_ensino].map(normalizar_texto),
                "turma_raw": df[col_turma],
                "tipo_etapa": etapas.map(lambda valor: valor["tipo_etapa"]),
                "ordem_etapa": etapas.map(lambda valor: valor["ordem_etapa"]),
                "flag_etapa_nao_mapeada": etapas.map(lambda valor: "SIM" if valor["flag_nao_mapeado"] else "NAO"),
            }
        )
        partes.append(base)

    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def classificar_duracao(tipo_etapa: str, maior_ordem: object) -> str:
    tipo = normalizar_texto(tipo_etapa).upper()
    if tipo == "ANUAL":
        return "ANUAL_3_SERIES"
    if tipo == "MODULAR" and pd.notna(maior_ordem):
        ordem = int(maior_ordem)
        if ordem == 2:
            return "MODULAR_2"
        if ordem == 3:
            return "MODULAR_3"
        if ordem == 4:
            return "MODULAR_4"
    return "REVISAR"


def consolidar_duracao(df_historico: pd.DataFrame) -> pd.DataFrame:
    base_valida = df_historico[df_historico["flag_etapa_nao_mapeada"] == "NAO"].copy()

    registros: list[dict[str, object]] = []
    for (curso_canonico, tipo_ensino), grupo in base_valida.groupby(
        ["curso_canonico", "tipo_ensino"], dropna=False
    ):
        tipos_etapa = sorted(set(grupo["tipo_etapa"].dropna().map(normalizar_texto)))
        tipo_etapa_principal = tipos_etapa[0] if len(tipos_etapa) == 1 else "AMBIGUO"
        maior_ordem = pd.to_numeric(grupo["ordem_etapa"], errors="coerce").max()
        quantidade_semestres = grupo["periodo_referencia"].nunique()
        etapas_encontradas = " | ".join(
            sorted(
                set(
                    grupo["turma_raw"]
                    .dropna()
                    .map(normalizar_texto)
                )
            )
        )

        if tipo_etapa_principal == "ANUAL":
            duracao_inferida = 3
        elif tipo_etapa_principal == "MODULAR" and pd.notna(maior_ordem):
            duracao_inferida = int(maior_ordem)
        else:
            duracao_inferida = pd.NA

        classificacao = classificar_duracao(tipo_etapa_principal, duracao_inferida)
        flag_ambiguo = "SIM" if len(tipos_etapa) != 1 else "NAO"
        flag_sem_confianca = "SIM" if (
            flag_ambiguo == "SIM"
            or classificacao == "REVISAR"
            or quantidade_semestres < 2
            or (tipo_etapa_principal == "MODULAR" and pd.notna(duracao_inferida) and int(duracao_inferida) not in {2, 3, 4})
        ) else "NAO"

        registros.append(
            {
                "curso_canonico": curso_canonico,
                "tipo_ensino": tipo_ensino,
                "tipo_etapa_principal": tipo_etapa_principal,
                "maior_ordem_etapa_observada": maior_ordem,
                "duracao_inferida": duracao_inferida,
                "classificacao": classificacao,
                "quantidade_semestres_observados": quantidade_semestres,
                "exemplos_de_etapas_encontradas": etapas_encontradas,
                "flag_ambiguo": flag_ambiguo,
                "flag_sem_confianca": flag_sem_confianca,
            }
        )

    return pd.DataFrame(registros).sort_values(
        ["classificacao", "curso_canonico", "tipo_ensino"]
    )


def montar_resumo(df_duracao: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quantidade_cursos_anuais": int((df_duracao["classificacao"] == "ANUAL_3_SERIES").sum()),
                "quantidade_cursos_2_modulos": int((df_duracao["classificacao"] == "MODULAR_2").sum()),
                "quantidade_cursos_3_modulos": int((df_duracao["classificacao"] == "MODULAR_3").sum()),
                "quantidade_cursos_4_modulos": int((df_duracao["classificacao"] == "MODULAR_4").sum()),
                "quantidade_cursos_ambiguos": int((df_duracao["flag_ambiguo"] == "SIM").sum()),
                "quantidade_cursos_sem_confianca": int((df_duracao["flag_sem_confianca"] == "SIM").sum()),
            }
        ]
    )


def selecionar_cursos_ambiguos(df_duracao: pd.DataFrame) -> pd.DataFrame:
    return df_duracao[df_duracao["flag_ambiguo"] == "SIM"].copy()


def selecionar_cursos_sem_confianca(df_duracao: pd.DataFrame) -> pd.DataFrame:
    return df_duracao[df_duracao["flag_sem_confianca"] == "SIM"].copy()


def montar_exemplos(df_duracao: pd.DataFrame) -> pd.DataFrame:
    grupos = []
    for classificacao in ["ANUAL_3_SERIES", "MODULAR_2", "MODULAR_3", "MODULAR_4", "REVISAR"]:
        subset = df_duracao[df_duracao["classificacao"] == classificacao].head(10).copy()
        if not subset.empty:
            grupos.append(subset)
    return pd.concat(grupos, ignore_index=True) if grupos else pd.DataFrame()


def exportar(relatorio: dict[str, pd.DataFrame]) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        for aba, tabela in relatorio.items():
            tabela.to_excel(writer, sheet_name=aba, index=False)


def main() -> None:
    ref_cursos, ref_etapa = carregar_referencias()
    historico = consolidar_historico_alunos(ref_cursos, ref_etapa)
    duracao = consolidar_duracao(historico)

    relatorio = {
        "resumo": montar_resumo(duracao),
        "duracao_cursos": duracao,
        "cursos_ambiguos": selecionar_cursos_ambiguos(duracao),
        "cursos_sem_confianca": selecionar_cursos_sem_confianca(duracao),
        "exemplos": montar_exemplos(duracao),
    }
    exportar(relatorio)

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(relatorio["resumo"].to_string(index=False))


if __name__ == "__main__":
    main()
