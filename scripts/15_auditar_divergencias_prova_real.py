from __future__ import annotations

from pathlib import Path
import math
import sys

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from ared.normalizar import normalizar_texto  # noqa: E402


ARQ_VALIDACAO = RAIZ_PROJETO / "saida/VALIDACAO_PROVA_REAL_2026_2.xlsx"
ARQ_COORTES = RAIZ_PROJETO / "saida/coortes_historicas.xlsx"
ARQ_ALUNOS = RAIZ_PROJETO / "saida/base_alunos_historico.xlsx"
ARQ_VEST = RAIZ_PROJETO / "saida/base_vestibulinho_historico.xlsx"
ARQ_SAIDA = RAIZ_PROJETO / "saida/AUDITORIA_DIVERGENCIAS_PROVA_REAL.xlsx"

TOP_N = 20
ANO_REFERENCIA = 2026
SEMESTRE_REFERENCIA = 1


def carregar_bases() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    divergencias = pd.read_excel(ARQ_VALIDACAO, sheet_name="divergencias")
    coortes = pd.read_excel(ARQ_COORTES)
    alunos = pd.read_excel(ARQ_ALUNOS)
    vest = pd.read_excel(ARQ_VEST)
    return divergencias, coortes, alunos, vest


def preparar_top_divergencias(divergencias: pd.DataFrame) -> pd.DataFrame:
    top = divergencias.copy()
    top["abs_diferenca_acumulado"] = top["diferenca_acumulado"].abs()
    top = top.sort_values("abs_diferenca_acumulado", ascending=False).head(TOP_N).reset_index(drop=True)
    top["audit_id"] = [f"AUD_{indice + 1:02d}" for indice in range(len(top))]
    top["rank_divergencia"] = top.index + 1
    return top


def preparar_coortes(coortes: pd.DataFrame) -> pd.DataFrame:
    base = coortes.copy()
    base = base[
        (pd.to_numeric(base["ano"], errors="coerce") == ANO_REFERENCIA)
        & (pd.to_numeric(base["semestre"], errors="coerce") == SEMESTRE_REFERENCIA)
        & base["flag_coorte_completa"].map(normalizar_texto).str.upper().eq("SIM")
    ].copy()
    for coluna in ["op1_total_alunos", "op2_total_alunos", "op3_total_alunos", "op4_total_alunos"]:
        base[coluna] = pd.to_numeric(base[coluna], errors="coerce")
    return base


def preparar_alunos(alunos: pd.DataFrame) -> pd.DataFrame:
    base = alunos.copy()
    base = base[
        (pd.to_numeric(base["ano"], errors="coerce") == ANO_REFERENCIA)
        & (pd.to_numeric(base["semestre"], errors="coerce") == SEMESTRE_REFERENCIA)
    ].copy()
    base["ordem_etapa"] = pd.to_numeric(base["ordem_etapa"], errors="coerce")
    base["total_alunos"] = pd.to_numeric(base["total_alunos"], errors="coerce")
    return base


def preparar_vest(vest: pd.DataFrame) -> pd.DataFrame:
    base = vest.copy()
    base["ano"] = pd.to_numeric(base["ano"], errors="coerce")
    base["semestre"] = pd.to_numeric(base["semestre"], errors="coerce")
    base["vagas"] = pd.to_numeric(base["vagas"], errors="coerce")
    base["inscritos"] = pd.to_numeric(base["inscritos"], errors="coerce")
    base["demanda_num"] = (
        base["demanda"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    )
    base["demanda_num"] = pd.to_numeric(base["demanda_num"], errors="coerce")
    return base


def inferir_semestre_entrada(ano: int, semestre: int, ordem_etapa: float | int | None) -> tuple[int | None, int | None]:
    if ordem_etapa is None or pd.isna(ordem_etapa):
        return None, None
    deslocamento = int(ordem_etapa) - 1
    indice = (int(ano) * 2 + (int(semestre) - 1)) - deslocamento
    if indice < 0:
        return None, None
    return indice // 2, (indice % 2) + 1


def formatar_historico(op1: object, op2: object, op3: object, op4: object) -> str:
    partes: list[str] = []
    for rotulo, valor in [("OP1", op1), ("OP2", op2), ("OP3", op3), ("OP4", op4)]:
        if pd.notna(valor):
            partes.append(f"{rotulo}={int(valor) if float(valor).is_integer() else round(float(valor), 3)}")
    return " | ".join(partes)


def formatar_historico_alunos(grupo: pd.DataFrame) -> str:
    if grupo.empty:
        return ""
    base = grupo.sort_values("ordem_etapa")
    partes = []
    for _, linha in base.iterrows():
        etapa = normalizar_texto(linha["etapa"])
        total = linha["total_alunos"]
        if pd.notna(total):
            valor = int(total) if float(total).is_integer() else round(float(total), 3)
            partes.append(f"{etapa}={valor}")
    return " | ".join(partes)


def distancia_modulos(registro: dict[str, object] | pd.Series, linha_gabarito: pd.Series) -> float:
    mapa = [
        ("op1_total_alunos", "OP 1"),
        ("op2_total_alunos", "2o Módulo"),
        ("op3_total_alunos", "3o Módulo"),
        ("op4_total_alunos", "4o Módulo"),
    ]
    soma = 0.0
    comparacoes = 0
    for col_candidato, col_gabarito in mapa:
        valor_candidato = registro.get(col_candidato)
        valor_gabarito = linha_gabarito.get(col_gabarito)
        if pd.notna(valor_candidato) and pd.notna(valor_gabarito):
            soma += abs(float(valor_candidato) - float(valor_gabarito))
            comparacoes += 1
    return soma if comparacoes else math.nan


def buscar_vestibulinho_relacionado(
    linha_coorte: pd.Series,
    vest: pd.DataFrame,
    permitir_periodo_alternativo: bool = False,
) -> pd.DataFrame:
    ano_entrada, semestre_entrada = inferir_semestre_entrada(
        ANO_REFERENCIA,
        SEMESTRE_REFERENCIA,
        linha_coorte.get("ordem_etapa"),
    )
    if ano_entrada is None or semestre_entrada is None:
        return vest.iloc[0:0].copy()

    filtro = (
        (vest["ano"] == ano_entrada)
        & (vest["semestre"] == semestre_entrada)
        & vest["unidade_canonica"].eq(linha_coorte["unidade_canonica"])
        & vest["curso_canonico"].eq(linha_coorte["curso_canonico"])
        & vest["tipo_ensino"].eq(linha_coorte["tipo_ensino"])
    )
    if not permitir_periodo_alternativo:
        filtro &= vest["periodo"].eq(linha_coorte["periodo"])
    return vest.loc[filtro].copy()


def resumir_vestibulinho(df_vest: pd.DataFrame) -> tuple[float | None, float | None, float | None, str]:
    if df_vest.empty:
        return None, None, None, ""
    vagas = pd.to_numeric(df_vest["vagas"], errors="coerce").sum(min_count=1)
    inscritos = pd.to_numeric(df_vest["inscritos"], errors="coerce").sum(min_count=1)
    demanda = pd.to_numeric(df_vest["demanda_num"], errors="coerce").mean()
    detalhes = " || ".join(
        (
            df_vest["ano"].astype("Int64").astype(str)
            + "."
            + df_vest["semestre"].astype("Int64").astype(str)
            + " | "
            + df_vest["unidade_original"].map(normalizar_texto)
            + " | vagas="
            + df_vest["vagas"].fillna(0).astype(int).astype(str)
            + " | inscritos="
            + df_vest["inscritos"].fillna(0).astype(int).astype(str)
        ).tolist()
    )
    return vagas, inscritos, demanda, detalhes


def agregar_candidatos(grupo: pd.DataFrame) -> dict[str, object]:
    agregado: dict[str, object] = {
        "op1_total_alunos": pd.to_numeric(grupo["op1_total_alunos"], errors="coerce").fillna(0).sum(),
        "op2_total_alunos": pd.to_numeric(grupo["op2_total_alunos"], errors="coerce").fillna(0).sum(),
        "op3_total_alunos": pd.to_numeric(grupo["op3_total_alunos"], errors="coerce").fillna(0).sum(),
        "op4_total_alunos": pd.to_numeric(grupo["op4_total_alunos"], errors="coerce").fillna(0).sum(),
    }
    return agregado


def classificar_hipotese(
    linha_top: pd.Series,
    candidatas_exatas: pd.DataFrame,
    melhor_exata_alternativa: pd.Series | None,
    melhor_periodo: pd.Series | None,
    dist_escolhida: float,
    dist_agregada: float,
) -> tuple[str, str, str]:
    qtd_exatas = len(candidatas_exatas)
    multiplas_unidades_raw = candidatas_exatas["unidade_original"].nunique(dropna=False) > 1 if qtd_exatas else False
    periodo_alternativo_melhor = (
        melhor_periodo is not None
        and normalizar_texto(melhor_periodo["periodo"]) != normalizar_texto(linha_top["periodo"])
        and pd.notna(melhor_periodo["module_distance"])
        and (pd.isna(dist_escolhida) or melhor_periodo["module_distance"] + 5 < dist_escolhida)
    )
    exata_alternativa_melhor = (
        melhor_exata_alternativa is not None
        and pd.notna(melhor_exata_alternativa["module_distance"])
        and (pd.isna(dist_escolhida) or melhor_exata_alternativa["module_distance"] + 5 < dist_escolhida)
    )
    agregacao_melhor = (
        qtd_exatas > 1
        and pd.notna(dist_agregada)
        and (pd.isna(dist_escolhida) or dist_agregada + 5 < dist_escolhida)
    )

    if agregacao_melhor:
        return (
            "agrupamento institucional",
            "diferença de granularidade/unidade",
            "A soma das coortes exatas aproxima mais os módulos do gabarito do que a coorte escolhida pelo pipeline.",
        )
    if exata_alternativa_melhor:
        return (
            "outra turma candidata",
            "turma alternativa na mesma chave canônica",
            "Existe outra coorte com a mesma chave canônica e distância de módulos menor em relação ao gabarito.",
        )
    if periodo_alternativo_melhor:
        return (
            "match incorreto",
            "diferença de período",
            "Uma coorte do mesmo curso/unidade/tipo de ensino, mas em outro período, aproxima melhor os módulos do gabarito.",
        )
    if qtd_exatas > 1 or multiplas_unidades_raw:
        return (
            "regra de consolidação",
            "múltiplas linhas compartilham a mesma chave canônica",
            "Há mais de uma coorte completa na mesma chave canônica, sugerindo consolidação institucional diferente da granularidade do pipeline.",
        )
    if linha_top["abs_diferenca_acumulado"] >= 0.5:
        return (
            "possível erro no gabarito",
            "distância estrutural muito alta",
            "Mesmo sem alternativas mais aderentes, os módulos do gabarito permanecem muito distantes da coorte escolhida.",
        )
    return (
        "outro",
        "sem padrão dominante",
        "A divergência existe, mas não houve evidência suficiente para isolar um padrão estrutural dominante.",
    )


def montar_auditoria(
    top: pd.DataFrame,
    coortes: pd.DataFrame,
    alunos: pd.DataFrame,
    vest: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    top_rows: list[dict[str, object]] = []
    candidatos_rows: list[dict[str, object]] = []
    hipoteses_rows: list[dict[str, object]] = []

    for _, linha_top in top.iterrows():
        audit_id = linha_top["audit_id"]
        filtro_exato = (
            coortes["unidade_canonica"].eq(linha_top["unidade_canonica"])
            & coortes["curso_canonico"].eq(linha_top["curso_canonico"])
            & coortes["periodo"].eq(linha_top["periodo"])
            & coortes["tipo_ensino"].eq(linha_top["tipo_ensino"])
        )
        candidatas_exatas = coortes.loc[filtro_exato].copy()

        filtro_mesma_linha = filtro_exato & coortes["unidade_original"].eq(linha_top["unidade_original"]) & coortes["etapa"].eq(linha_top["etapa"])
        escolhida = coortes.loc[filtro_mesma_linha].copy()
        if escolhida.empty and not candidatas_exatas.empty:
            escolhida = candidatas_exatas.iloc[[0]].copy()
        linha_escolhida = escolhida.iloc[0] if not escolhida.empty else pd.Series(dtype=object)

        historico_pipeline = formatar_historico(
            linha_escolhida.get("op1_total_alunos"),
            linha_escolhida.get("op2_total_alunos"),
            linha_escolhida.get("op3_total_alunos"),
            linha_escolhida.get("op4_total_alunos"),
        )

        alunos_pipeline = alunos[
            (alunos["unidade_original"].eq(linha_top["unidade_original"]))
            & (alunos["curso_canonico"].eq(linha_top["curso_canonico"]))
            & (alunos["periodo"].eq(linha_top["periodo"]))
            & (alunos["tipo_ensino"].eq(linha_top["tipo_ensino"]))
        ].copy()
        historico_alunos_pipeline = formatar_historico_alunos(alunos_pipeline)

        vest_pipeline = buscar_vestibulinho_relacionado(linha_escolhida, vest) if not linha_escolhida.empty else vest.iloc[0:0].copy()
        vagas_alt, inscritos_alt, demanda_alt, detalhe_vest_pipeline = resumir_vestibulinho(vest_pipeline)

        dist_escolhida = distancia_modulos(linha_escolhida, linha_top) if not linha_escolhida.empty else math.nan

        for _, candidata in candidatas_exatas.iterrows():
            dist = distancia_modulos(candidata, linha_top)
            vest_candidata = buscar_vestibulinho_relacionado(candidata, vest)
            vagas, inscritos, demanda, detalhe_vest = resumir_vestibulinho(vest_candidata)
            candidatos_rows.append(
                {
                    "audit_id": audit_id,
                    "candidate_scope": "mesma_chave_individual",
                    "is_pipeline_choice": bool(
                        normalizar_texto(candidata["unidade_original"]) == normalizar_texto(linha_top["unidade_original"])
                        and normalizar_texto(candidata["etapa"]) == normalizar_texto(linha_top["etapa"])
                    ),
                    "unidade_original": candidata["unidade_original"],
                    "unidade_canonica": candidata["unidade_canonica"],
                    "curso_canonico": candidata["curso_canonico"],
                    "tipo_oferta": candidata["tipo_oferta"],
                    "periodo": candidata["periodo"],
                    "tipo_ensino": candidata["tipo_ensino"],
                    "etapa": candidata["etapa"],
                    "ordem_etapa": candidata["ordem_etapa"],
                    "duracao_coorte": candidata["duracao_coorte"],
                    "op1_total_alunos": candidata["op1_total_alunos"],
                    "op2_total_alunos": candidata["op2_total_alunos"],
                    "op3_total_alunos": candidata["op3_total_alunos"],
                    "op4_total_alunos": candidata["op4_total_alunos"],
                    "historico_longitudinal": formatar_historico(
                        candidata["op1_total_alunos"],
                        candidata["op2_total_alunos"],
                        candidata["op3_total_alunos"],
                        candidata["op4_total_alunos"],
                    ),
                    "module_distance": dist,
                    "vagas_relacionadas": vagas,
                    "inscritos_relacionados": inscritos,
                    "demanda_media_relacionada": demanda,
                    "vestibulinho_relacionado": detalhe_vest,
                }
            )

        dist_agregada = math.nan
        if len(candidatas_exatas) > 1:
            agregado = agregar_candidatos(candidatas_exatas)
            dist_agregada = distancia_modulos(agregado, linha_top)
            vest_agregado_partes = []
            vagas_sum = 0.0
            inscritos_sum = 0.0
            demandas: list[float] = []
            for _, candidata in candidatas_exatas.iterrows():
                vest_candidata = buscar_vestibulinho_relacionado(candidata, vest)
                vagas, inscritos, demanda, detalhe_vest = resumir_vestibulinho(vest_candidata)
                if vagas is not None:
                    vagas_sum += vagas
                if inscritos is not None:
                    inscritos_sum += inscritos
                if demanda is not None and not pd.isna(demanda):
                    demandas.append(float(demanda))
                if detalhe_vest:
                    vest_agregado_partes.append(detalhe_vest)
            candidatos_rows.append(
                {
                    "audit_id": audit_id,
                    "candidate_scope": "mesma_chave_agrupada",
                    "is_pipeline_choice": False,
                    "unidade_original": "AGREGADO_EXATO",
                    "unidade_canonica": linha_top["unidade_canonica"],
                    "curso_canonico": linha_top["curso_canonico"],
                    "tipo_oferta": "MULTIPLO",
                    "periodo": linha_top["periodo"],
                    "tipo_ensino": linha_top["tipo_ensino"],
                    "etapa": "AGRUPADO",
                    "ordem_etapa": None,
                    "duracao_coorte": None,
                    "op1_total_alunos": agregado["op1_total_alunos"],
                    "op2_total_alunos": agregado["op2_total_alunos"],
                    "op3_total_alunos": agregado["op3_total_alunos"],
                    "op4_total_alunos": agregado["op4_total_alunos"],
                    "historico_longitudinal": formatar_historico(
                        agregado["op1_total_alunos"],
                        agregado["op2_total_alunos"],
                        agregado["op3_total_alunos"],
                        agregado["op4_total_alunos"],
                    ),
                    "module_distance": dist_agregada,
                    "vagas_relacionadas": vagas_sum if vest_agregado_partes else None,
                    "inscritos_relacionados": inscritos_sum if vest_agregado_partes else None,
                    "demanda_media_relacionada": sum(demandas) / len(demandas) if demandas else None,
                    "vestibulinho_relacionado": " || ".join(vest_agregado_partes),
                }
            )

        filtro_periodo_alt = (
            coortes["unidade_canonica"].eq(linha_top["unidade_canonica"])
            & coortes["curso_canonico"].eq(linha_top["curso_canonico"])
            & coortes["tipo_ensino"].eq(linha_top["tipo_ensino"])
            & ~coortes["periodo"].eq(linha_top["periodo"])
        )
        candidatas_periodo = coortes.loc[filtro_periodo_alt].copy()
        for _, candidata in candidatas_periodo.iterrows():
            dist = distancia_modulos(candidata, linha_top)
            vest_candidata = buscar_vestibulinho_relacionado(candidata, vest, permitir_periodo_alternativo=True)
            vagas, inscritos, demanda, detalhe_vest = resumir_vestibulinho(vest_candidata)
            candidatos_rows.append(
                {
                    "audit_id": audit_id,
                    "candidate_scope": "periodo_alternativo",
                    "is_pipeline_choice": False,
                    "unidade_original": candidata["unidade_original"],
                    "unidade_canonica": candidata["unidade_canonica"],
                    "curso_canonico": candidata["curso_canonico"],
                    "tipo_oferta": candidata["tipo_oferta"],
                    "periodo": candidata["periodo"],
                    "tipo_ensino": candidata["tipo_ensino"],
                    "etapa": candidata["etapa"],
                    "ordem_etapa": candidata["ordem_etapa"],
                    "duracao_coorte": candidata["duracao_coorte"],
                    "op1_total_alunos": candidata["op1_total_alunos"],
                    "op2_total_alunos": candidata["op2_total_alunos"],
                    "op3_total_alunos": candidata["op3_total_alunos"],
                    "op4_total_alunos": candidata["op4_total_alunos"],
                    "historico_longitudinal": formatar_historico(
                        candidata["op1_total_alunos"],
                        candidata["op2_total_alunos"],
                        candidata["op3_total_alunos"],
                        candidata["op4_total_alunos"],
                    ),
                    "module_distance": dist,
                    "vagas_relacionadas": vagas,
                    "inscritos_relacionados": inscritos,
                    "demanda_media_relacionada": demanda,
                    "vestibulinho_relacionado": detalhe_vest,
                }
            )

        candidatos_auditoria = pd.DataFrame([linha for linha in candidatos_rows if linha["audit_id"] == audit_id])
        exatas_individuais = candidatos_auditoria[candidatos_auditoria["candidate_scope"] == "mesma_chave_individual"].copy()
        exatas_alternativas = exatas_individuais[~exatas_individuais["is_pipeline_choice"]].copy()
        melhor_exata_alternativa = (
            exatas_alternativas.sort_values("module_distance").iloc[0]
            if not exatas_alternativas.empty
            else None
        )
        melhor_periodo = (
            candidatos_auditoria[candidatos_auditoria["candidate_scope"] == "periodo_alternativo"]
            .sort_values("module_distance")
            .iloc[0]
            if not candidatos_auditoria[candidatos_auditoria["candidate_scope"] == "periodo_alternativo"].empty
            else None
        )

        hipotese, padrao, explicacao = classificar_hipotese(
            linha_top,
            candidatas_exatas,
            melhor_exata_alternativa,
            melhor_periodo,
            dist_escolhida,
            dist_agregada,
        )

        melhor_candidato_desc = ""
        if melhor_periodo is not None and (
            pd.isna(dist_escolhida) or melhor_periodo["module_distance"] < dist_escolhida
        ):
            melhor_candidato_desc = (
                f"Periodo alternativo {melhor_periodo['periodo']} | {melhor_periodo['unidade_original']} | dist_mod={round(float(melhor_periodo['module_distance']), 3)}"
            )
        elif melhor_exata_alternativa is not None:
            melhor_candidato_desc = (
                f"Outra coorte exata | {melhor_exata_alternativa['unidade_original']} | dist_mod={round(float(melhor_exata_alternativa['module_distance']), 3)}"
            )
        elif pd.notna(dist_agregada):
            melhor_candidato_desc = f"Agrupamento exato | dist_mod={round(float(dist_agregada), 3)}"

        top_rows.append(
            {
                "audit_id": audit_id,
                "rank_divergencia": linha_top["rank_divergencia"],
                "semestre_referencia_pipeline": linha_top["semestre_referencia_pipeline_pipeline"],
                "semestre_publicacao_ared": linha_top["semestre_publicacao_ared_pipeline"],
                "unidade_canonica": linha_top["unidade_canonica"],
                "curso_canonico": linha_top["curso_canonico"],
                "periodo": linha_top["periodo"],
                "tipo_ensino": linha_top["tipo_ensino"],
                "tipo_oferta_pipeline": linha_top["tipo_oferta"],
                "turma_reconstruida_pipeline": linha_top["unidade_original"],
                "etapa_pipeline": linha_top["etapa"],
                "historico_longitudinal_pipeline": historico_pipeline,
                "historico_alunos_base": historico_alunos_pipeline,
                "op2_percentual_pipeline": linha_top["op2_percentual"],
                "op3_percentual_pipeline": linha_top["op3_percentual"],
                "op4_percentual_pipeline": linha_top["op4_percentual"],
                "acumulado_pipeline": linha_top["acumulado_percentual"],
                "nivel_pipeline": linha_top["nivel_ared"],
                "diagnostico_pipeline": linha_top["diagnostico_ared"],
                "op1_gabarito": linha_top["OP 1"],
                "op2_gabarito_total": linha_top["2o Módulo"],
                "op3_gabarito_total": linha_top["3o Módulo"],
                "op4_gabarito_total": linha_top["4o Módulo"],
                "op2_percentual_gabarito": linha_top["gabarito_op2_percentual"],
                "op3_percentual_gabarito": linha_top["gabarito_op3_percentual"],
                "op4_percentual_gabarito": linha_top["gabarito_op4_percentual"],
                "acumulado_gabarito": linha_top["gabarito_acumulado_percentual"],
                "nivel_gabarito": linha_top["gabarito_nivel_ared"],
                "diagnostico_gabarito": linha_top["gabarito_diagnostico_ared"],
                "diferenca_op2": linha_top["diferenca_op2"],
                "diferenca_op3": linha_top["diferenca_op3"],
                "diferenca_op4": linha_top["diferenca_op4"],
                "diferenca_acumulado": linha_top["diferenca_acumulado"],
                "abs_diferenca_acumulado": linha_top["abs_diferenca_acumulado"],
                "module_distance_pipeline": dist_escolhida,
                "qtd_candidatas_mesma_chave": len(candidatas_exatas),
                "qtd_periodos_alternativos": candidatas_periodo["periodo"].nunique(dropna=False),
                "vagas_pipeline_relacionadas": vagas_alt,
                "inscritos_pipeline_relacionados": inscritos_alt,
                "demanda_pipeline_relacionada": demanda_alt,
                "vestibulinho_pipeline_relacionado": detalhe_vest_pipeline,
                "melhor_candidato_identificado": melhor_candidato_desc,
                "hipotese_principal": hipotese,
                "padrao_estrutural": padrao,
                "evidencia_principal": explicacao,
            }
        )

        hipoteses_rows.append(
            {
                "audit_id": audit_id,
                "rank_divergencia": linha_top["rank_divergencia"],
                "unidade_canonica": linha_top["unidade_canonica"],
                "curso_canonico": linha_top["curso_canonico"],
                "periodo": linha_top["periodo"],
                "tipo_ensino": linha_top["tipo_ensino"],
                "hipotese_principal": hipotese,
                "padrao_estrutural": padrao,
                "qtd_candidatas_mesma_chave": len(candidatas_exatas),
                "qtd_unidades_originais_mesma_chave": candidatas_exatas["unidade_original"].nunique(dropna=False),
                "module_distance_pipeline": dist_escolhida,
                "module_distance_agrupado_exato": dist_agregada,
                "melhor_periodo_alternativo": melhor_periodo["periodo"] if melhor_periodo is not None else "",
                "distancia_melhor_periodo_alternativo": melhor_periodo["module_distance"] if melhor_periodo is not None else None,
                "evidencia_principal": explicacao,
            }
        )

    top_divergencias = pd.DataFrame(top_rows)
    candidatos_alternativos = pd.DataFrame(candidatos_rows)
    hipoteses = pd.DataFrame(hipoteses_rows)

    frequencias = hipoteses["hipotese_principal"].value_counts(dropna=False).rename_axis("hipotese_principal").reset_index(name="frequencia")
    padroes = top_divergencias["padrao_estrutural"].value_counts(dropna=False).rename_axis("padrao_estrutural").reset_index(name="frequencia")
    principais_descobertas = pd.DataFrame(
        [
            {
                "tipo": "padrão",
                "descricao": "Múltiplas divergências apresentam distância estrutural alta entre os módulos do pipeline e os totais do gabarito.",
            },
            {
                "tipo": "hipótese",
                "descricao": "Casos com mais de uma coorte na mesma chave canônica sugerem consolidação institucional ou granularidade diferente.",
            },
            {
                "tipo": "hipótese",
                "descricao": "Casos com período alternativo mais aderente sugerem chave canônica insuficiente para reproduzir o gabarito institucional.",
            },
        ]
    )
    resumo_auditoria = pd.concat(
        [
            pd.DataFrame(
                [
                    {
                        "secao": "geral",
                        "categoria": "top_divergencias_auditadas",
                        "valor": len(top_divergencias),
                    },
                    {
                        "secao": "geral",
                        "categoria": "media_abs_diferenca_acumulado",
                        "valor": top_divergencias["abs_diferenca_acumulado"].mean(),
                    },
                    {
                        "secao": "geral",
                        "categoria": "mediana_abs_diferenca_acumulado",
                        "valor": top_divergencias["abs_diferenca_acumulado"].median(),
                    },
                ]
            ),
            frequencias.rename(columns={"hipotese_principal": "categoria", "frequencia": "valor"}).assign(secao="hipotese_principal"),
            padroes.rename(columns={"padrao_estrutural": "categoria", "frequencia": "valor"}).assign(secao="padrao_estrutural"),
            principais_descobertas.rename(columns={"tipo": "secao", "descricao": "categoria"}).assign(valor=""),
        ],
        ignore_index=True,
    )

    return top_divergencias, candidatos_alternativos, hipoteses, resumo_auditoria


def exportar_abas(relatorio: dict[str, pd.DataFrame]) -> None:
    ARQ_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine="openpyxl") as writer:
        for nome_aba, tabela in relatorio.items():
            tabela.to_excel(writer, sheet_name=nome_aba, index=False)


def main() -> None:
    divergencias, coortes, alunos, vest = carregar_bases()
    top = preparar_top_divergencias(divergencias)
    coortes_prep = preparar_coortes(coortes)
    alunos_prep = preparar_alunos(alunos)
    vest_prep = preparar_vest(vest)

    top_divergencias, candidatos_alternativos, hipoteses, resumo_auditoria = montar_auditoria(
        top,
        coortes_prep,
        alunos_prep,
        vest_prep,
    )

    relatorio = {
        "top_divergencias": top_divergencias,
        "candidatos_alternativos": candidatos_alternativos,
        "hipoteses": hipoteses,
        "resumo_auditoria": resumo_auditoria,
    }
    exportar_abas(relatorio)

    print(f"Arquivo gerado: {ARQ_SAIDA}")
    print(top_divergencias[["audit_id", "unidade_canonica", "curso_canonico", "hipotese_principal"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
