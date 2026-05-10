# AREd ETL

Projeto de ETL em Python para consolidacao, normalizacao, validacao e reconstrucao de bases relacionadas ao AREd, com foco em insumos academicos, referencias de cadastro e geracao de planilhas de saida para analise operacional.

Repositorio GitHub: https://github.com/RafaelWRuiz/ared-etl

## Objetivo do projeto

Organizar um fluxo reprodutivel para:

- carregar bases brutas de alunos, vestibulinho e referencias;
- normalizar cursos, unidades, periodos e etapas;
- aplicar regras de negocio do AREd;
- gerar bases intermediarias, validacoes e relatorios em Excel;
- apoiar consumo posterior em analise operacional e Power BI.

## Arquitetura simplificada

O projeto segue uma arquitetura simples em camadas:

1. `dados_brutos/`
   - arquivos de entrada, modelos e referencias.
2. `ared/`
   - nucleo Python com funcoes de carga, normalizacao, validacao, indicadores, exportacao e regras de negocio.
3. `scripts/` e scripts na raiz
   - pontos de execucao para etapas especificas do pipeline e analises auxiliares.
4. `saida/`
   - artefatos gerados pelo ETL, incluindo staging, curated, validacoes, inventarios e relatorios finais.
5. `tests/`
   - testes automatizados das regras implementadas.

Fluxo resumido:

`dados_brutos` / `cadastros` -> `ared` + `scripts` -> `saida`

## Etapas ja implementadas

Pelo estado atual do repositorio, ja existem etapas para:

- inspecao inicial de arquivos e modelos;
- geracao de staging normalizado;
- geracao de bases curated;
- validacao de calculos e regras de negocio;
- auditoria de origem de indicadores;
- inventario de bases historicas;
- inferencia de duracao de cursos;
- reconstrucao de coortes e trajetorias longitudinais.

## Estrutura de pastas

```text
ared_etl/
|-- ared/                # nucleo do projeto
|-- cadastros/           # tabelas auxiliares e mapeamentos mantidos no repositorio
|-- dados_brutos/        # arquivos de entrada, referencias e modelos
|   |-- alunos/
|   |-- modelos/
|   |-- referencias/
|   |-- regras/
|   `-- vestibulinho/
|-- saida/               # artefatos gerados pelo ETL
|   |-- curated/
|   |-- documentacao/
|   |-- inventario/
|   |-- staging/
|   `-- validacao/
|-- scripts/             # execucoes por etapa
|-- tests/               # testes automatizados
|-- gerar_ared.py        # exemplo de ponto de entrada
|-- requirements.txt
`-- README.md
```

## Stack utilizada

- Python 3
- pandas
- openpyxl
- pytest
- Excel como formato principal de entrada/saida
- Power BI como camada analitica de consumo posterior

## Status atual

Status: em estruturacao para versionamento Git/GitHub.

Situacao observada neste momento:

- o nucleo Python em `ared/` ja esta separado das entradas e das saidas;
- os scripts do pipeline estao majoritariamente organizados em `scripts/`;
- existem testes automatizados iniciais em `tests/`;
- a pasta `saida/` concentra artefatos gerados e, por isso, foi configurada para nao ser versionada por padrao;
- o repositorio agora passa a ter documentacao inicial e regras basicas de versionamento.

## Observacoes

- Este README descreve a estrutura atual sem alterar a logica de negocio do AREd.
- O versionamento recomendado e de codigo, cadastros e referencias controladas, evitando commitar artefatos gerados e caches locais.
