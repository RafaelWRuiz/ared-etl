from pathlib import Path
import pandas as pd

ARQUIVO = Path("saida/TIPOS_CURSO.xlsx")

df = pd.read_excel(ARQUIVO, sheet_name="dados")

df["ANO_ENTRADA"] = (
    df["Código da Turma"]
    .astype(str)
    .str.extract(r"^(\d{4}\.\d)")
)

resultado = (
    df.groupby(["TIPO_CURSO", "ANO_ENTRADA"])
    .size()
    .reset_index(name="quantidade")
    .sort_values(
        ["TIPO_CURSO", "ANO_ENTRADA"]
    )
)

print(resultado)

saida = Path("saida/VALIDACAO_SEMESTRES.xlsx")

with pd.ExcelWriter(saida) as writer:
    resultado.to_excel(
        writer,
        sheet_name="validacao",
        index=False
    )

print(f"\nArquivo gerado: {saida}")