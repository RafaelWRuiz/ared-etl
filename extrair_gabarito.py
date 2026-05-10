from pathlib import Path
import pandas as pd

ARQUIVO_MODELO = Path("dados_brutos/modelos/ARED_2026_1_MODELO.xlsx")
ABA_GABARITO = "Relatório ARED 2026.1"

PASTA_SAIDA = Path("saida")
PASTA_SAIDA.mkdir(exist_ok=True)

df = pd.read_excel(
    ARQUIVO_MODELO,
    sheet_name=ABA_GABARITO,
    header=4
)

print("Gabarito carregado com sucesso.")
print(f"Linhas: {len(df)}")
print(f"Colunas: {len(df.columns)}")

print("\nColunas encontradas:")
for col in df.columns:
    print("-", col)

print("\nPrimeiras linhas:")
print(df.head())

df.to_excel(
    PASTA_SAIDA / "GABARITO_ARED_2026_1.xlsx",
    index=False
)

print("\nArquivo gerado: saida/GABARITO_ARED_2026_1.xlsx")