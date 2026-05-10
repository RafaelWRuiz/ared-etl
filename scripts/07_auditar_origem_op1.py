from __future__ import annotations

from pathlib import Path
import sys
import unicodedata

import pandas as pd


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from ared.normalizar import normalizar_texto


ARQ_VALIDACAO_OP1 = RAIZ_PROJETO / 'saida/validacao/VALIDACAO_OP1.xlsx'
ARQ_ALUNOS = RAIZ_PROJETO / 'saida/curated/fato_alunos_turma_semestre.xlsx'
ARQ_GABARITO_2026_1 = RAIZ_PROJETO / 'saida/GABARITO_ARED_2026_1.xlsx'
DIR_SAIDA = RAIZ_PROJETO / 'saida/validacao'
ARQ_SAIDA = DIR_SAIDA / 'AUDITORIA_ORIGEM_OP1.xlsx'


def normalizar_nome_coluna(nome: str) -> str:
    texto = unicodedata.normalize('NFKD', normalizar_texto(nome))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return texto.upper()


def resolver_coluna(df: pd.DataFrame, nome_esperado: str) -> str:
    mapa = {normalizar_nome_coluna(col): col for col in df.columns}
    chave = normalizar_nome_coluna(nome_esperado)
    if chave not in mapa:
        raise KeyError(f'Coluna obrigatoria nao encontrada: {nome_esperado}')
    return mapa[chave]


def carregar() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    validacao = pd.read_excel(ARQ_VALIDACAO_OP1, sheet_name='validacao_op1')
    alunos = pd.read_excel(ARQ_ALUNOS)
    gabarito = pd.read_excel(ARQ_GABARITO_2026_1)
    return validacao, alunos, gabarito


def preparar_alunos(df: pd.DataFrame) -> pd.DataFrame:
    col_flag = resolver_coluna(df, 'flag_entrada')
    alunos = df[df[col_flag].map(normalizar_texto) == 'SIM'].copy()
    for coluna in ['codigo_unidade_canonico', 'curso_canonico', 'periodo_canonico', 'tipo_ensino', 'tipo_local_oferta']:
        alunos[f'{coluna}_norm'] = alunos[coluna].map(normalizar_texto)
    alunos['total_alunos_num'] = pd.to_numeric(alunos['total_alunos'], errors='coerce')
    return alunos


def auditar_caso(caso: pd.Series, alunos: pd.DataFrame) -> dict[str, object]:
    filtros = {
        'codigo_unidade_canonico_norm': normalizar_texto(caso['codigo_unidade_canonico']),
        'curso_canonico_norm': normalizar_texto(caso['curso_canonico']),
        'periodo_canonico_norm': normalizar_texto(caso['periodo_canonico']),
        'tipo_ensino_norm': normalizar_texto(caso['tipo_ensino']),
        'tipo_local_oferta_norm': normalizar_texto(caso['tipo_local_oferta']),
    }
    hipoteses = {
        'A': ['codigo_unidade_canonico_norm', 'curso_canonico_norm', 'periodo_canonico_norm', 'tipo_ensino_norm', 'tipo_local_oferta_norm'],
        'B': ['codigo_unidade_canonico_norm', 'curso_canonico_norm', 'periodo_canonico_norm', 'tipo_ensino_norm'],
        'C': ['codigo_unidade_canonico_norm', 'curso_canonico_norm', 'periodo_canonico_norm'],
        'D': ['codigo_unidade_canonico_norm', 'curso_canonico_norm'],
    }
    esperado = pd.to_numeric(caso['op1_esperado'], errors='coerce')
    resultado = {
        'gabarito_key': caso['gabarito_key'],
        'codigo_unidade_canonico': caso['codigo_unidade_canonico'],
        'curso_canonico': caso['curso_canonico'],
        'periodo_canonico': caso['periodo_canonico'],
        'tipo_ensino': caso['tipo_ensino'],
        'tipo_local_oferta': caso['tipo_local_oferta'],
        'curso_raw': caso.get('curso_raw', ''),
        'curso_raw_gabarito': caso.get('curso_raw_gabarito', ''),
        'vagas': pd.to_numeric(caso.get('vagas_calculado'), errors='coerce'),
        'op1_esperado': esperado,
        'op1_calculado_original': pd.to_numeric(caso.get('op1_calculado'), errors='coerce'),
        'diferenca_op1_original': pd.to_numeric(caso.get('diferenca_op1'), errors='coerce'),
        'gabarito_vagas_esperado': pd.to_numeric(caso.get('vagas_esperado'), errors='coerce'),
    }
    classificacoes = []
    melhor = {'hipotese': '', 'tipo': 'NENHUM', 'diff': float('inf')}
    for nome, chaves in hipoteses.items():
        mask = pd.Series(True, index=alunos.index)
        for chave in chaves:
            mask &= alunos[chave] == filtros[chave]
        candidatos = alunos.loc[mask].copy()
        qtd = len(candidatos)
        soma = candidatos['total_alunos_num'].sum() if qtd else pd.NA
        maior = candidatos['total_alunos_num'].max() if qtd else pd.NA
        menor = candidatos['total_alunos_num'].min() if qtd else pd.NA
        linha_unica_bate = bool(qtd and (candidatos['total_alunos_num'] == esperado).any())
        soma_bate = bool(qtd and pd.notna(esperado) and pd.notna(soma) and float(soma) == float(esperado))
        menores_diffs = (candidatos['total_alunos_num'] - esperado).abs() if qtd and pd.notna(esperado) else pd.Series(dtype='float64')
        melhor_linha = candidatos.loc[menores_diffs.idxmin(), 'total_alunos_num'] if not menores_diffs.empty else pd.NA
        diff_melhor_linha = float(menores_diffs.min()) if not menores_diffs.empty else pd.NA
        diff_soma = abs(float(soma) - float(esperado)) if qtd and pd.notna(esperado) and pd.notna(soma) else pd.NA
        turmas = ' | '.join(candidatos['numero_turma'].astype(str).head(5).tolist()) if qtd else ''
        resultado[f'hipotese_{nome}_qtd_candidatos'] = qtd
        resultado[f'hipotese_{nome}_soma_total_alunos'] = soma
        resultado[f'hipotese_{nome}_maior_total_alunos'] = maior
        resultado[f'hipotese_{nome}_menor_total_alunos'] = menor
        resultado[f'hipotese_{nome}_linha_unica_bate'] = 'SIM' if linha_unica_bate else 'NAO'
        resultado[f'hipotese_{nome}_soma_bate'] = 'SIM' if soma_bate else 'NAO'
        resultado[f'hipotese_{nome}_melhor_linha_total_alunos'] = melhor_linha
        resultado[f'hipotese_{nome}_diff_melhor_linha'] = diff_melhor_linha
        resultado[f'hipotese_{nome}_diff_soma'] = diff_soma
        resultado[f'hipotese_{nome}_exemplo_turmas'] = turmas
        if linha_unica_bate:
            classificacoes.append(f'LINHA_UNICA_{nome}')
            if melhor['diff'] > 0:
                melhor = {'hipotese': nome, 'tipo': 'LINHA_UNICA', 'diff': 0.0}
        if soma_bate:
            classificacoes.append(f'SOMA_{nome}')
            if melhor['diff'] > 0:
                melhor = {'hipotese': nome, 'tipo': 'SOMA_TURMAS', 'diff': 0.0}
        if not linha_unica_bate and not soma_bate:
            if pd.notna(diff_melhor_linha) and diff_melhor_linha < melhor['diff']:
                melhor = {'hipotese': nome, 'tipo': 'APROX_LINHA', 'diff': float(diff_melhor_linha)}
            if pd.notna(diff_soma) and diff_soma < melhor['diff']:
                melhor = {'hipotese': nome, 'tipo': 'APROX_SOMA', 'diff': float(diff_soma)}
    resultado['hipoteses_que_batem'] = ' | '.join(classificacoes)
    resultado['hipotese_melhor_ajuste'] = melhor['hipotese'] or 'NENHUM'
    resultado['padrao_melhor_ajuste'] = melhor['tipo']
    resultado['melhor_diff_absoluta'] = melhor['diff'] if melhor['diff'] != float('inf') else pd.NA
    return resultado


def montar_relatorio(auditoria: pd.DataFrame) -> dict[str, pd.DataFrame]:
    casos_soma_bate = auditoria[auditoria['hipoteses_que_batem'].str.contains('SOMA_', na=False)].copy()
    casos_linha_unica_bate = auditoria[auditoria['hipoteses_que_batem'].str.contains('LINHA_UNICA_', na=False)].copy()
    casos_nenhum_bate = auditoria[auditoria['hipoteses_que_batem'] == ''].copy()
    resumo_hipoteses = (
        auditoria.groupby(['hipotese_melhor_ajuste', 'padrao_melhor_ajuste'])
        .size()
        .reset_index(name='quantidade')
        .sort_values('quantidade', ascending=False)
    )

    resumo = pd.DataFrame([{
        'casos_divergentes_auditados': len(auditoria),
        'casos_linha_unica_bate': len(casos_linha_unica_bate),
        'casos_soma_bate': len(casos_soma_bate),
        'casos_nenhum_bate': len(casos_nenhum_bate),
        'hipotese_mais_frequente': auditoria['padrao_melhor_ajuste'].mode().iloc[0] if not auditoria.empty else 'NENHUM',
    }])

    resumo_tipo_local = auditoria.groupby(['tipo_local_oferta', 'padrao_melhor_ajuste']).size().reset_index(name='quantidade').sort_values(['tipo_local_oferta','quantidade'], ascending=[True, False])
    resumo_tipo_ensino = auditoria.groupby(['tipo_ensino', 'padrao_melhor_ajuste']).size().reset_index(name='quantidade').sort_values(['tipo_ensino','quantidade'], ascending=[True, False])

    exemplos = pd.concat([
        casos_linha_unica_bate.head(10),
        casos_soma_bate.head(10),
        casos_nenhum_bate.head(10),
    ], ignore_index=True)

    return {
        'resumo': resumo,
        'auditoria_detalhada': auditoria,
        'casos_soma_bate': casos_soma_bate,
        'casos_linha_unica_bate': casos_linha_unica_bate,
        'casos_nenhum_bate': casos_nenhum_bate,
        'resumo_hipoteses': resumo_hipoteses,
        'resumo_tipo_local': resumo_tipo_local,
        'resumo_tipo_ensino': resumo_tipo_ensino,
        'exemplos_explicativos': exemplos,
    }


def exportar(relatorio: dict[str, pd.DataFrame]) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ARQ_SAIDA, engine='openpyxl') as writer:
        for aba, tabela in relatorio.items():
            tabela.to_excel(writer, sheet_name=aba, index=False)


def main() -> None:
    validacao, alunos, _gabarito = carregar()
    divergentes = validacao[(validacao['op1_esperado'].notna()) & (~validacao['aderente_2_casas'].fillna(False))].copy()
    alunos = preparar_alunos(alunos)
    auditoria = pd.DataFrame([auditar_caso(caso, alunos) for _, caso in divergentes.iterrows()])
    relatorio = montar_relatorio(auditoria)
    exportar(relatorio)
    print(f'Arquivo gerado: {ARQ_SAIDA}')
    print(relatorio['resumo'].to_string(index=False))


if __name__ == '__main__':
    main()
