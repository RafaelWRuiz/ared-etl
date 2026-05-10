from __future__ import annotations

from ared.regras_negocio import (
    calcular_semestre_entrada as calcular_semestre_entrada_regras,
    detectar_tipo_curso,
)


def semestre_anterior(semestre: str, passos: int = 1) -> str:
    """
    Volta N semestres.

    Exemplo:
    2026_1, 1 -> 2025_2
    2026_1, 2 -> 2025_1
    2026_1, 3 -> 2024_2
    """
    ano_txt, periodo_txt = semestre.split("_")
    ano = int(ano_txt)
    periodo = int(periodo_txt)

    for _ in range(passos):
        if periodo == 1:
            ano -= 1
            periodo = 2
        else:
            periodo = 1

    return f"{ano}_{periodo}"


def ano_anterior(semestre: str, anos: int = 1) -> str:
    """
    Volta anos mantendo o mesmo semestre.
    """
    ano_txt, periodo_txt = semestre.split("_")
    ano = int(ano_txt) - anos
    return f"{ano}_{periodo_txt}"


def calcular_semestre_entrada(
    semestre_final: str,
    tipo_curso: str,
    quantidade_modulos: int | None,
) -> str:
    """
    Adaptador para a regra central de negócio usando o formato AAAA_S.
    """
    ano_txt, periodo_txt = semestre_final.split("_")
    resultado = calcular_semestre_entrada_regras(
        ano_referencia=int(ano_txt),
        semestre_referencia=int(periodo_txt),
        tipo_curso=detectar_tipo_curso(tipo_curso),
        quantidade_modulos=quantidade_modulos,
    )
    return resultado.replace(".", "_")
