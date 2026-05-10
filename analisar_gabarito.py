from pathlib import Path
import pandas as pd

ARQUIVO_GABARITO = Path("saida/GABARITO_ARED_2026_1.xlsx")
PASTA_SAIDA = Path("saida")
PASTA_SAIDA.mkdir(exist_ok=True)

df = pd.read_excel(ARQUIVO_GABARITO)

analises = {}

analises["resumo"] = pd.DataFrame([{
    "linhas": len(df),
    "colunas": len(df.columns),
    "codigos_turma_unicos": df["Código da Turma"].nunique(),
    "unidades_unicas": df["Unidades do CEETEPS"].nunique(),
    "cursos_unicos": df["Habilitação/Curso"].nunique(),
    "periodos_unicos": df["Período"].nunique(),
}])

analises["periodos"] = (
    df["Período"]
    .value_counts(dropna=False)
    .reset_index()
)
analises["periodos"].columns = ["Período", "quantidade"]

analises["indicadores"] = (
    df["Indicador"]
    .value_counts(dropna=False)
    .reset_index()
)
analises["indicadores"].columns = ["Indicador", "quantidade"]

analises["diagnosticos"] = (
    df["Diagnóstico"]
    .value_counts(dropna=False)
    .reset_index()
)
analises["diagnosticos"].columns = ["Diagnóstico", "quantidade"]

analises["anos_entrada"] = (
    df["Código da Turma"]
    .astype(str)
    .str.extract(r"^(\d{4}\.\d)")
    .value_counts()
    .reset_index()
)
analises["anos_entrada"].columns = ["Ano/Semestre", "quantidade"]

analises["top_cursos"] = (
    df["Habilitação/Curso"]
    .value_counts(dropna=False)
    .head(50)
    .reset_index()
)
analises["top_cursos"].columns = ["Habilitação/Curso", "quantidade"]

with pd.ExcelWriter(PASTA_SAIDA / "ANALISE_GABARITO.xlsx") as writer:
    for nome_aba, tabela in analises.items():
        tabela.to_excel(writer, sheet_name=nome_aba, index=False)

print("Análise do gabarito gerada com sucesso.")
print("Arquivo: saida/ANALISE_GABARITO.xlsx")
print("\nResumo:")
print(analises["resumo"])