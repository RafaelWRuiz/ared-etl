import pytest

from ared.regras_negocio import calcular_semestre_entrada, detectar_tipo_curso
from ared.semestres import semestre_anterior


def test_semestre_anterior():
    assert semestre_anterior("2026_1", 1) == "2025_2"
    assert semestre_anterior("2026_1", 2) == "2025_1"
    assert semestre_anterior("2026_1", 3) == "2024_2"


@pytest.mark.parametrize(
    ("nome_curso", "tipo_esperado"),
    [
        (
            "Ensino Médio com Habilitação Profissional de Técnico em Desenvolvimento de Sistemas - MTec - AMS",
            "ANUAL_AMS",
        ),
        (
            "Ensino Médio com Habilitação Profissional de Técnico em Eletrônica - MTec",
            "ANUAL_MTEC",
        ),
        (
            "Ensino Médio com Itinerário Formativo de Matemática e suas Tecnologias",
            "ANUAL_MEDIO",
        ),
        ("Desenvolvimento de Sistemas", "MODULAR"),
    ],
)
def test_detectar_tipo_curso(nome_curso, tipo_esperado):
    assert detectar_tipo_curso(nome_curso) == tipo_esperado


@pytest.mark.parametrize("tipo", ["ANUAL_AMS", "ANUAL_MEDIO", "ANUAL_MTEC"])
def test_cursos_anuais_entram_em_2023_1_para_ared_2026_1(tipo):
    assert calcular_semestre_entrada(2026, 1, tipo) == "2023.1"


def test_modular_2_modulos_entra_em_2024_2_para_ared_2026_1():
    assert calcular_semestre_entrada(2026, 1, "MODULAR", quantidade_modulos=2) == "2024.2"


def test_modular_3_modulos_entra_em_2024_1_para_ared_2026_1():
    assert calcular_semestre_entrada(2026, 1, "MODULAR", quantidade_modulos=3) == "2024.1"


def test_modular_4_modulos_entra_em_2023_2_para_ared_2026_1():
    assert calcular_semestre_entrada(2026, 1, "MODULAR", quantidade_modulos=4) == "2023.2"


def test_modular_sem_quantidade_de_modulos_falha():
    with pytest.raises(ValueError):
        calcular_semestre_entrada(2026, 1, "MODULAR")


def test_modular_com_quantidade_de_modulos_invalida_falha():
    with pytest.raises(ValueError):
        calcular_semestre_entrada(2026, 1, "MODULAR", quantidade_modulos=5)
