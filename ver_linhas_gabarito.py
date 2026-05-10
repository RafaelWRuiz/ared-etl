from pathlib import Path
import pandas as pd

ARQUIVO_MODELO = Path("dados_brutos/modelos/ARED_2026_1_MODELO.xlsx")
ABA_GABARITO = "Relatório ARED 2026.1"

df = pd.read_excel(
    ARQUIVO_MODELO,
    sheet_name=ABA_GABARITO,
    header=None
)

print("Primeiras 20 linhas da aba:")
print("=" * 80)

for i in range(20):
    valores = df.iloc[i].tolist()
    valores_limpos = [str(v) if pd.notna(v) else "" for v in valores]
    print(f"\nLINHA {i}:")
    print(valores_limpos)