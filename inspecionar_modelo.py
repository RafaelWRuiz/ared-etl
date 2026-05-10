from pathlib import Path
import pandas as pd

ARQUIVO_MODELO = Path("dados_brutos/modelos/ARED_2026_1_MODELO.xlsx")
PASTA_SAIDA = Path("saida")
PASTA_SAIDA.mkdir(exist_ok=True)

xls = pd.ExcelFile(ARQUIVO_MODELO)

resumo = []

print("Abas encontradas:")
for aba in xls.sheet_names:
    df = pd.read_excel(ARQUIVO_MODELO, sheet_name=aba)
    resumo.append({
        "aba": aba,
        "linhas": len(df),
        "colunas": len(df.columns),
        "nomes_colunas": " | ".join(map(str, df.columns)),
    })
    print(f"- {aba}: {len(df)} linhas, {len(df.columns)} colunas")

df_resumo = pd.DataFrame(resumo)
df_resumo.to_excel(PASTA_SAIDA / "INSPECAO_MODELO.xlsx", index=False)

print("\nArquivo gerado: saida/INSPECAO_MODELO.xlsx")