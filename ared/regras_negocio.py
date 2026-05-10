from __future__ import annotations

import unicodedata


TIPOS_ANUAIS = {
    "ANUAL_AMS",
    "ANUAL_MEDIO",
    "ANUAL_MTEC",
}


def normalizar_texto(texto: str) -> str:
    texto_normalizado = unicodedata.normalize("NFKD", str(texto))
    texto_sem_acentos = "".join(
        caractere for caractere in texto_normalizado if not unicodedata.combining(caractere)
    )
    return texto_sem_acentos.upper().strip()


def detectar_tipo_curso(nome_curso: str) -> str:
    nome = normalizar_texto(nome_curso)

    if "AMS" in nome:
        return "ANUAL_AMS"

    if "MTEC" in nome:
        return "ANUAL_MTEC"

    if "ENSINO MEDIO" in nome:
        return "ANUAL_MEDIO"

    return "MODULAR"


def retroceder_semestres(ano: int, semestre: int, passos: int) -> str:
    ano_atual = ano
    semestre_atual = semestre

    for _ in range(passos):
        if semestre_atual == 1:
            ano_atual -= 1
            semestre_atual = 2
        else:
            semestre_atual = 1

    return f"{ano_atual}.{semestre_atual}"


def calcular_semestre_entrada(
    ano_referencia: int,
    semestre_referencia: int,
    tipo_curso: str,
    quantidade_modulos: int | None = None,
) -> str:
    """
    Regras validadas contra o gabarito institucional ARED 2026.1.

    - ANUAL_MTEC, ANUAL_AMS e ANUAL_MEDIO: coorte 2023.1 para ARED 2026.1
      => retrocesso de 6 semestres.
    - MODULAR 2 módulos: coorte 2024.2 para ARED 2026.1
      => retrocesso de 3 semestres.
    - MODULAR 3 módulos: coorte 2024.1 para ARED 2026.1
      => retrocesso de 4 semestres.
    - MODULAR 4 módulos: coorte 2023.2 para ARED 2026.1
      => retrocesso de 5 semestres.
    """
    if semestre_referencia not in {1, 2}:
        raise ValueError(f"Semestre de referência inválido: {semestre_referencia}")

    tipo_normalizado = normalizar_texto(tipo_curso)

    if tipo_normalizado in TIPOS_ANUAIS:
        return retroceder_semestres(ano_referencia, semestre_referencia, passos=6)

    if tipo_normalizado != "MODULAR":
        raise ValueError(f"Tipo de curso inválido: {tipo_curso}")

    if quantidade_modulos not in {2, 3, 4}:
        raise ValueError(
            "Quantidade de módulos inválida para curso modular. Valores aceitos: 2, 3 ou 4."
        )

    return retroceder_semestres(
        ano_referencia,
        semestre_referencia,
        passos=quantidade_modulos + 1,
    )
