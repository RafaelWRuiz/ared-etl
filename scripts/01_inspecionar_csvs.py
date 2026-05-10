from pathlib import Path
import pandas as pd

PASTA_DADOS = Path("dados_brutos")
PASTA_SAIDA = Path("saida")
PASTA_SAIDA.mkdir(exist_ok=True)

ARQUIVOS = [
    Path("dados_brutos/vestibulinho/1sem2026.csv"),
    Path("dados_brutos/alunos/totais_alunos_1sem2026.csv"),
]

def ler_csv(caminho: Path) -> pd.DataFrame:
    tentativas = [
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "latin1"},
    ]

    for config in tentativas:
        try:
            df = pd.read_csv(caminho, **config)
            if len(df.columns) > 1:
                print(f"Lido com sucesso: {caminho.name} | sep={config['sep']} | encoding={config['encoding']}")
                return df
        except Exception:
            pass

    raise ValueError(f"Não consegui ler o arquivo: {caminho}")

resumos = []

with pd.ExcelWriter(PASTA_SAIDA / "INSPECAO_CSVS.xlsx") as writer:
    for arquivo in ARQUIVOS:
        df = ler_csv(arquivo)

        resumo = pd.DataFrame([{
            "arquivo": arquivo.name,
            "linhas": len(df),
            "colunas": len(df.columns),
            "nomes_colunas": " | ".join(df.columns.astype(str)),
        }])

        resumos.append(resumo)

        resumo.to_excel(writer, sheet_name=f"{arquivo.stem[:25]}_resumo", index=False)

        pd.DataFrame({
            "coluna": df.columns,
            "tipo": [str(df[col].dtype) for col in df.columns],
            "nulos": [df[col].isna().sum() for col in df.columns],
            "valores_unicos": [df[col].nunique(dropna=True) for col in df.columns],
        }).to_excel(writer, sheet_name=f"{arquivo.stem[:25]}_colunas", index=False)

        df.head(20).to_excel(writer, sheet_name=f"{arquivo.stem[:25]}_amostra", index=False)

    pd.concat(resumos, ignore_index=True).to_excel(writer, sheet_name="resumo_geral", index=False)

print("Inspeção concluída.")
print("Arquivo gerado: saida/INSPECAO_CSVS.xlsx")