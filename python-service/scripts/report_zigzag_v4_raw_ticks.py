"""Produce an offline interactive report from the frozen raw-tick experiment."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import spearmanr

from scripts.research_zigzag_v4_raw_ticks import iso, metrics


def block_interval(rows_a, rows_b, start, end):
    """Paired daily P&L, moving 7-calendar-day blocks, fixed random seed."""
    day0 = start//86400000
    n = end//86400000-day0+1
    delta = np.zeros(n)
    for sign,rows in ((1,rows_a),(-1,rows_b)):
        for row in rows:
            day=row["exit_ms"]//86400000-day0
            if 0<=day<n:
                delta[day]+=sign*row["r"]
    rng=np.random.default_rng(20260913)
    totals=[]
    for _ in range(2000):
        starts=rng.integers(0,max(1,n-6),size=(n+6)//7)
        ix=np.concatenate([np.arange(s,min(s+7,n)) for s in starts])[:n]
        totals.append(float(delta[ix].sum()))
    return {"method":"paired daily R, moving blocks of 7 calendar days, 2000 resamples, seed 20260913",
            "delta_net_r":float(delta.sum()),"ci95_net_r":np.quantile(totals,[.025,.975]).tolist()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    args=p.parse_args()
    root=args.directory
    report=json.loads((root/'report.json').read_text())
    trades=json.loads((root/'trades.json').read_text())
    audit=json.loads((root/'historical_audit.json').read_text())
    split=int(datetime.fromisoformat(report['selection_end_utc']).timestamp()*1000)
    end=int(datetime.fromisoformat(report['observed_end_utc']).timestamp()*1000)
    sufficiently_sampled = [x['name'] for x in report['candidates'][1:]
                            if report['results'][x['name']+':base']['training']['trades'] >= 50]
    chosen=report['selected_on_training'] or max(
        sufficiently_sampled, key=lambda n: report['results'][n+':base']['training']['expectancy_r'])
    def held(rows):
        return [x for x in rows if x['entry_ms']>=split]
    interval=block_interval(held(trades[chosen+':base']),held(trades['v3_ticks:base']),split,end)
    correlations={}
    for name,rows in [('archived_v3',audit),('v3_ticks',trades['v3_ticks:base']),('diagnostic_v4',trades[chosen+':base'])]:
        x=np.array([r['range60'] for r in rows])
        y=np.array([r['r'] for r in rows])
        correlations[name]={
            'range_vs_signed_r':float(spearmanr(x,y).statistic) if len(rows)>2 else None,
            'range_vs_absolute_r':float(spearmanr(x,abs(y)).statistic) if len(rows)>2 else None,
            'range_winners_mean':float(x[y>0].mean()) if (y>0).any() else None,
            'range_losers_mean':float(x[y<0].mean()) if (y<0).any() else None,
        }
    same=[dict(x,r=x['same_timestamp_tick_r']) for x in audit if 'same_timestamp_tick_r' in x]
    by_day={x['day']:x for x in report['coverage']}
    requested_start=datetime.fromisoformat(report['requested_start_utc'])
    requested_end=datetime.fromisoformat(report['anchor_close_utc'])
    missing=[]
    day=requested_start.date()
    while day<=requested_end.date():
        if day.weekday()<5 and day.isoformat() not in by_day:
            missing.append(day.isoformat())
        day+=timedelta(days=1)
    tail=[x for x in missing if x>report['observed_end_utc'][:10]]
    missing_inside=[x for x in missing if x<=report['observed_end_utc'][:10]]
    monthly={}
    for name,rows in [('archived_v3',audit),('v3_ticks',trades['v3_ticks:base']),('diagnostic_v4',trades[chosen+':base'])]:
        monthly[name]={m:metrics([x for x in rows if iso(x['entry_ms'])[:7]==m]) for m in sorted({iso(x['entry_ms'])[:7] for x in rows})}
    diagnostics={'selected_diagnostic':chosen,'holdout_difference_bootstrap':interval,
                 'correlations_descriptive_not_causal':correlations,
                 'same_timestamp_tick_repricing':metrics(same),'historical_matched_original':metrics(audit),
                 'missing_weekdays_tail':tail,'missing_weekdays_inside':missing_inside,
                 'monthly':monthly,
                 'archived_top10_by_money':sorted(audit,key=lambda x:x['original_net_pnl'],reverse=True)[:10],
                 'archived_bottom10_by_money':sorted(audit,key=lambda x:x['original_net_pnl'])[:10],
                 'trades_with_exit_quote_gap_over_60s':{k:sum(x['max_quote_gap_ms']>60000 for x in rows) for k,rows in trades.items()}}
    (root/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2,allow_nan=False)+'\n')
    fig=make_subplots(rows=2,cols=2,subplot_titles=(
        'Resultado acumulado em R — ticks, risco constante',
        'Resultado médio por operação — treino / avaliação posterior',
        'V3 arquivada: range anterior e resultado em R',
        'V3: mesmas datas de entrada, saídas refeitas com ticks'))
    for name,rows in [('V3 ticks',trades['v3_ticks:base']),('V4 '+chosen,trades[chosen+':base']),('V4 custos adversos',trades[chosen+':stress'])]:
        rows=sorted(rows,key=lambda x:x['exit_ms'])
        fig.add_trace(go.Scatter(x=[iso(x['exit_ms']) for x in rows],y=np.cumsum([x['r'] for x in rows]),name=name,mode='lines'),row=1,col=1)
    names=[x['name'] for x in report['candidates']]
    for period,label in [('training','Treino'),('holdout','Avaliação posterior')]:
        fig.add_trace(go.Bar(x=names,y=[report['results'][n+':base'][period]['expectancy_r'] for n in names],name=label),row=1,col=2)
    fig.add_trace(go.Scatter(x=[x['range60'] for x in audit],y=[x['r'] for x in audit],mode='markers',name='Trades arquivados',
                            text=[iso(x['entry_ms']) for x in audit],marker={'size':5,'opacity':.5}),row=2,col=1)
    fig.add_trace(go.Scatter(x=[x['r'] for x in audit if 'same_timestamp_tick_r' in x],
                            y=[x['same_timestamp_tick_r'] for x in audit if 'same_timestamp_tick_r' in x],mode='markers',name='Mesma entrada, outro replay',
                            text=[iso(x['entry_ms']) for x in audit if 'same_timestamp_tick_r' in x],marker={'size':5,'opacity':.5}),row=2,col=2)
    fig.update_layout(title=f'ZigZag V4 — {report["total_ticks"]:,} ticks | decisão: {report["decision"]}',height=1000,template='plotly_white')
    fig.update_xaxes(title_text='Range médio dos 60 M5 anteriores (USD/oz)',row=2,col=1)
    fig.update_xaxes(title_text='R arquivado',row=2,col=2)
    fig.update_yaxes(title_text='R refeito com ticks',row=2,col=2)
    fig.write_html(root/'analise-interativa.html',include_plotlyjs=True,full_html=True)
    lines=[
        '# ZigZag Scalper V4 — análise de ticks e experimento', '',
        f'Dataset congelado: `{report["dataset"]}`. Decisão do teste: **{report["decision"]}**.', '',
        f'Janela solicitada: {report["requested_start_utc"]} a {report["anchor_close_utc"]}.',
        f'Ticks efetivamente disponíveis: {report["observed_start_utc"]} a {report["observed_end_utc"]}; **{report["total_ticks"]:,} observações**, {len(by_day)} partições diárias.',
        'O candle mais recente foi consultado em `market_history` (XAUUSD/M5): abertura 2026-09-11 20:50 UTC, fechamento 20:55 UTC. A tabela `market_ticks` retornou vazia. Consulta HTTP à Dukascopy para os dias faltantes expirou.',
        f'Dias úteis sem partição no final: {", ".join(tail) or "nenhum"}. Dias úteis sem partição dentro da cobertura (incluem possíveis feriados): {", ".join(missing_inside) or "nenhum"}.',
        '**O teste não cobre integralmente o ano solicitado. Os dias ausentes não foram preenchidos com candles nem com outro broker.**', '',
        '## Método', '',
        'Pivôs fractais de M30 confirmados por duas barras posteriores completas; nenhum pivô futuro. O contexto M5 contém apenas barras já encerradas; o preço do candle corrente é o midpoint do tick atual. A V3 usa range médio de 60 M5, limiar 6 USD/oz e filtros estruturais originais na expansão.',
        'Sinais avaliados em todos os ticks. Uma entrada por M5 e uma posição aberta por variante. V4 exige também o Bid acima do pivô para compra, ou Ask abaixo para venda. Persistência reinicia ao voltar para dentro do pivô ou mudar o M5.',
        'Stop V1: 2,40 USD/oz, alvo 10,00, breakeven 0,40, trailing 1,20/0,60, máximo 600 s. Expansão V2: stop 0,60, alvo 10,00, breakeven 0,40/+0,01, trailing 0,40/0,20, máximo 60 s.',
        'Variante de volatilidade: stop = clip(0,5 × range60; 0,60; 4,80), breakeven = stop/6, trailing = stop/2 e stop/4; lote ajustado para manter US$24 de risco. Variante eficiência: eficiência do caminho de ticks em 30 s >=0,15, movimento alinhado em 5 s >= spread e extensão limitada.',
        'Compra no Ask, venda no Bid, encerramento na cotação oposta. Comissão de US$4,50/lote, contrato de 100 oz/lote, risco fixo US$24, lote fracionário teórico. Base: 250 ms e 0,02 USD/oz de slippage por execução a mercado; stress: 1 s e 0,05. Stops atravessados são preenchidos no preço observado, não no preço ideal do stop.',
        f'Seleção até {report["selection_end_utc"]}; posições que cruzam a fronteira são excluídas da seleção. Ranking somente no treino: lucro R / máximo drawdown R, mínimo 50 trades e PF >1,05. Nenhum ajuste após inspeção da avaliação posterior.',
        'O período posterior é fora da seleção deste experimento, mas já apareceu em pesquisas anteriores do projeto; não é uma amostra de mercado nunca examinada.', '',
        '## Comparação', '',
        '| Variante | N treino | PF treino | R treino | N posterior | PF posterior | R posterior | DD posterior (R) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for n in names:
        a=report['results'][n+':base']['training']
        b=report['results'][n+':base']['holdout']
        lines.append(f'| {n} | {a["trades"]} | {a["profit_factor"]} | {a["net_r"]} | {b["trades"]} | {b["profit_factor"]} | {b["net_r"]} | {b["max_drawdown_r"]} |')
    lines += ['',f'Candidata qualificada no treino: `{report["selected_on_training"]}`. Variante para diagnóstico entre as que têm pelo menos 50 trades, escolhida pela maior expectativa no treino: `{chosen}`. O campo `best_training_diagnostic` do JSON bruto inclui também a variante de apenas oito trades, que não é elegível.',
              f'Stress posterior dessa variante: {json.dumps(report["results"][chosen+":stress"]["holdout"],ensure_ascii=False)}.',
              f'Diferença V4 − V3 em R no período posterior: {interval["delta_net_r"]:.2f}; intervalo bootstrap de 95%: [{interval["ci95_net_r"][0]:.2f}, {interval["ci95_net_r"][1]:.2f}]. Reamostragem conjunta de blocos de sete dias, 2.000 repetições, seed fixa; não é garantia de resultado futuro.', '',
              '## Volatilidade e operações extremas', '',
              '**Proveniência que muda a interpretação:** o snapshot operacional atual da V3 declara `strategy_version=repriced_zero_spread_commission_4.5`. Seu campo `note` diz que o spread foi reprecificado de 10 para zero pips mantendo entradas e saídas congeladas. Portanto, esse resultado não representa execução no Bid/Ask observado.',
              'A V1 vem do replay em candles; a V2 também possui estudos de saídas em ticks com spread modelado. A V3 arquivada combina essas fontes. A afirmação de que V1 e V2 seriam ambas exclusivamente calculadas por candles não descreve todos os artefatos atuais.',
              'Fontes da auditoria: `data/backtests-operational/core-zigzag-v3-365.json`, `scripts/build_zigzag_v3_replay.py`, `scripts/cache_tick_research_snapshots.py`, `scripts/reprice_tick_replay_costs.py`. Este último preserva timestamps de saída ao mudar o spread, sem reconstruir o acionamento dos stops.',
              f'{len(audit)} de {report["historical_total_in_requested_window"]} operações arquivadas no intervalo tiveram contexto de ticks pareado.',
              f'Resultado arquivado pareado: {json.dumps(metrics(audit))}. Mesmos instantes de entrada com execução refeita em ticks: {json.dumps(metrics(same))}. Os sinais arquivados são tratados como dados para auditoria; esse comparativo não valida a causalidade das entradas originais.',
              'Correlação de Spearman entre range anterior e resultado (R), e entre range e magnitude |R|:',
              '```json',json.dumps(correlations,indent=2),'```','',
              'Quartis de volatilidade da V3 arquivada, com limites calculados somente no treino:', '',
              '| Quartil | N | PF | R líquido | R médio |', '|---|---:|---:|---:|---:|']
    g=report['descriptive_volatility_groups']['archived_v3']['range60']
    for i,q in enumerate(g['quartiles']):
        m=q['overall']
        lines.append(f'| Q{i+1} | {m["trades"]} | {m["profit_factor"]} | {m["net_r"]} | {m["expectancy_r"]} |')
    lines += ['',f'Limites dos quartis (USD/oz): {g["training_quartile_edges"]}. Associação descritiva, não causalidade; direção, horário e tendência também variam.', '',
              'Maiores ganhos e perdas por resultado monetário no snapshot operacional:', '',
              '| Grupo | Entrada UTC | Resultado original (US$) | R original | Range60 | Spread | R refeito em ticks |',
              '|---|---|---:|---:|---:|---:|---:|']
    for label,rows in [('Ganho',diagnostics['archived_top10_by_money'][:5]),('Perda',diagnostics['archived_bottom10_by_money'][:5])]:
        for x in rows:
            lines.append(f'| {label} | {iso(x["entry_ms"])} | {x["original_net_pnl"]:.2f} | {x["r"]:.3f} | {x["range60"]:.3f} | {x["spread"]:.3f} | {x.get("same_timestamp_tick_r",0):.3f} |')
    lines += ['', '## Limites e reprodução','',
              'A reconstrução V3 em ticks usa M30 completos e um candle corrente explícito. O replay/EA antigo tem convenções de janela diferentes. Assim, é uma baseline causal reconstruída, não paridade certificada com o EA. O EA também consulta a API a cada cinco segundos; os gatilhos de 500 ms/2 s exigiriam outra cadência antes de qualquer forward.',
              'A V4 anterior rejeitada permanece arquivada. Este experimento não altera catálogo, flags, execução demo/real ou curvas existentes.',
              *['- '+x for x in report['limitations']], '',
              '```bash', 'cd /home/codexops/projects/2Lotus/python-service',
              f'PYTHONPATH=. .venv/bin/python scripts/research_zigzag_v4_raw_ticks.py --anchor {report["anchor_close_utc"]} --release {report["dataset"]} --output {root}',
              f'PYTHONPATH=. .venv/bin/python scripts/report_zigzag_v4_raw_ticks.py {root}', '```', '',
              'Artefatos: `protocol.json`, `report.json`, `diagnostics.json`, `trades.json`, `historical_audit.json`, `analise-interativa.html`. Hashes de todos os arquivos de dados usados e do código estão no relatório/protocolo.']
    (root/'RELATORIO.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'chosen':chosen,'interval':interval,'correlations':correlations,
                      'same_entry':metrics(same),'archived':metrics(audit),'missing_tail':tail},indent=2))


if __name__=='__main__':
    main()
