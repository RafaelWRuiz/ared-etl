from pathlib import Path
import pandas as pd

ARQUIVO = Path("saida/GABARITO_ARED_2026_1.xlsx")

df = pd.read_excel(ARQUIVO)

def detectar_tipo(nome_curso: str) -> str:
    nome = str(nome_curso).upper()

    if "MTEC" in nome:
        return "ANUAL_MTEC"

    if "AMS" in nome:
        return "ANUAL_AMS"

    if "ENSINO MÉDIO" in nome:
        return "ANUAL_MEDIO"

    return "MODULAR"

df["TIPO_CURSO"] = df["Habilitação/Curso"].apply(detectar_tipo)

resultado = (
    df["TIPO_CURSO"]
    .value_counts()
    .reset_index()
)

resultado.columns = ["TIPO_CURSO", "quantidade"]

print(resultado)

print("\nExemplos:")
print(
    df[
        ["Habilitação/Curso", "TIPO_CURSO"]
    ].drop_duplicates().head(30)
)

saida = Path("saida/TIPOS_CURSO.xlsx")

with pd.ExcelWriter(saida) as writer:
    df.to_excel(writer, sheet_name="dados", index=False)
    resultado.to_excel(writer, sheet_name="resumo", index=False)

print(f"\nArquivo gerado: {saida}")