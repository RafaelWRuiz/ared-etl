from ared.regras_negocio import (
    detectar_tipo_curso,
    calcular_semestre_entrada
)

print("=" * 60)
print("TESTE 1 - CURSO ANUAL")
print("=" * 60)

curso = "Ensino Médio com Habilitação Profissional de Técnico em Administração - MTec"

tipo = detectar_tipo_curso(curso)

entrada = calcular_semestre_entrada(
    ano_referencia=2026,
    semestre_referencia=1,
    tipo_curso=tipo
)

print("Curso:", curso)
print("Tipo:", tipo)
print("Entrada calculada:", entrada)

print("\n")

print("=" * 60)
print("TESTE 2 - MODULAR 3 MÓDULOS")
print("=" * 60)

curso = "Desenvolvimento de Sistemas"

tipo = detectar_tipo_curso(curso)

entrada = calcular_semestre_entrada(
    ano_referencia=2026,
    semestre_referencia=1,
    tipo_curso=tipo,
    quantidade_modulos=3
)

print("Curso:", curso)
print("Tipo:", tipo)
print("Entrada calculada:", entrada)

print("\n")

print("=" * 60)
print("TESTE 3 - MODULAR 2 MÓDULOS")
print("=" * 60)

curso = "Segurança do Trabalho"

tipo = detectar_tipo_curso(curso)

entrada = calcular_semestre_entrada(
    ano_referencia=2026,
    semestre_referencia=1,
    tipo_curso=tipo,
    quantidade_modulos=2
)

print("Curso:", curso)
print("Tipo:", tipo)
print("Entrada calculada:", entrada)