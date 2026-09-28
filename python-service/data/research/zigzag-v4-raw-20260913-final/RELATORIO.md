# ZigZag Scalper V4 — análise de ticks e experimento

Dataset congelado: `20260911T043125Z-0ef1a31ba0a5`. Decisão do teste: **rejected**.

Janela solicitada: 2025-09-11T20:55:00+00:00 a 2026-09-11T20:55:00+00:00.
Ticks efetivamente disponíveis: 2025-09-11T20:55:00+00:00 a 2026-09-01T23:59:59.995000+00:00; **90,087,170 observações**, 304 partições diárias.
O candle mais recente foi consultado em `market_history` (XAUUSD/M5): abertura 2026-09-11 20:50 UTC, fechamento 20:55 UTC. A tabela `market_ticks` retornou vazia. Consulta HTTP à Dukascopy para os dias faltantes expirou.
Dias úteis sem partição no final: 2026-09-02, 2026-09-03, 2026-09-04, 2026-09-07, 2026-09-08, 2026-09-09, 2026-09-10, 2026-09-11. Dias úteis sem partição dentro da cobertura (incluem possíveis feriados): 2026-04-03.
**O teste não cobre integralmente o ano solicitado. Os dias ausentes não foram preenchidos com candles nem com outro broker.**

## Método

Pivôs fractais de M30 confirmados por duas barras posteriores completas; nenhum pivô futuro. O contexto M5 contém apenas barras já encerradas; o preço do candle corrente é o midpoint do tick atual. A V3 usa range médio de 60 M5, limiar 6 USD/oz e filtros estruturais originais na expansão.
Sinais avaliados em todos os ticks. Uma entrada por M5 e uma posição aberta por variante. V4 exige também o Bid acima do pivô para compra, ou Ask abaixo para venda. Persistência reinicia ao voltar para dentro do pivô ou mudar o M5.
Stop V1: 2,40 USD/oz, alvo 10,00, breakeven 0,40, trailing 1,20/0,60, máximo 600 s. Expansão V2: stop 0,60, alvo 10,00, breakeven 0,40/+0,01, trailing 0,40/0,20, máximo 60 s.
Variante de volatilidade: stop = clip(0,5 × range60; 0,60; 4,80), breakeven = stop/6, trailing = stop/2 e stop/4; lote ajustado para manter US$24 de risco. Variante eficiência: eficiência do caminho de ticks em 30 s >=0,15, movimento alinhado em 5 s >= spread e extensão limitada.
Compra no Ask, venda no Bid, encerramento na cotação oposta. Comissão de US$4,50/lote, contrato de 100 oz/lote, risco fixo US$24, lote fracionário teórico. Base: 250 ms e 0,02 USD/oz de slippage por execução a mercado; stress: 1 s e 0,05. Stops atravessados são preenchidos no preço observado, não no preço ideal do stop.
Seleção até 2026-03-12T20:55:00+00:00; posições que cruzam a fronteira são excluídas da seleção. Ranking somente no treino: lucro R / máximo drawdown R, mínimo 50 trades e PF >1,05. Nenhum ajuste após inspeção da avaliação posterior.
O período posterior é fora da seleção deste experimento, mas já apareceu em pesquisas anteriores do projeto; não é uma amostra de mercado nunca examinada.

## Comparação

| Variante | N treino | PF treino | R treino | N posterior | PF posterior | R posterior | DD posterior (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| v3_ticks | 742 | 0.2919 | -255.34 | 772 | 0.2698 | -282.3183 | 284.3746 |
| v4_quote_confirm | 586 | 0.3519 | -174.0771 | 637 | 0.2603 | -223.8413 | 224.8692 |
| v4_persist_500ms | 530 | 0.3362 | -153.7283 | 575 | 0.3024 | -179.8604 | 180.6346 |
| v4_persist_2000ms | 499 | 0.3297 | -145.3592 | 533 | 0.3449 | -151.3163 | 156.2529 |
| v4_efficiency | 8 | 1.1236 | 0.2858 | 19 | 0.303 | -4.2896 | 4.9229 |
| v4_volatility_scaled | 534 | 0.2873 | -188.0056 | 577 | 0.3002 | -180.0821 | 184.2575 |

Candidata qualificada no treino: `None`. Variante para diagnóstico entre as que têm pelo menos 50 trades, escolhida pela maior expectativa no treino: `v4_persist_500ms`. O campo `best_training_diagnostic` do JSON bruto inclui também a variante de apenas oito trades, que não é elegível.
Stress posterior dessa variante: {"trades": 578, "net_r": -215.9704, "net_usd_at_24_risk": -5183.29, "expectancy_r": -0.37365, "profit_factor": 0.2501, "win_rate_pct": 25.43, "max_drawdown_r": 220.1558, "worst_r": -5.4271, "best_r": 2.6979}.
Diferença V4 − V3 em R no período posterior: 102.46; intervalo bootstrap de 95%: [66.20, 143.73]. Reamostragem conjunta de blocos de sete dias, 2.000 repetições, seed fixa; não é garantia de resultado futuro.

## Volatilidade e operações extremas

**Proveniência que muda a interpretação:** o snapshot operacional atual da V3 declara `strategy_version=repriced_zero_spread_commission_4.5`. Seu campo `note` diz que o spread foi reprecificado de 10 para zero pips mantendo entradas e saídas congeladas. Portanto, esse resultado não representa execução no Bid/Ask observado.
A V1 vem do replay em candles; a V2 também possui estudos de saídas em ticks com spread modelado. A V3 arquivada combina essas fontes. A afirmação de que V1 e V2 seriam ambas exclusivamente calculadas por candles não descreve todos os artefatos atuais.
Fontes da auditoria: `data/backtests-operational/core-zigzag-v3-365.json`, `scripts/build_zigzag_v3_replay.py`, `scripts/cache_tick_research_snapshots.py`, `scripts/reprice_tick_replay_costs.py`. Este último preserva timestamps de saída ao mudar o spread, sem reconstruir o acionamento dos stops.
686 de 708 operações arquivadas no intervalo tiveram contexto de ticks pareado.
Resultado arquivado pareado: {"trades": 686, "net_r": 255.0971, "net_usd_at_24_risk": 6122.33, "expectancy_r": 0.37186, "profit_factor": 1.8398, "win_rate_pct": 56.12, "max_drawdown_r": 14.0229, "worst_r": -3.6583, "best_r": 8.965}. Mesmos instantes de entrada com execução refeita em ticks: {"trades": 680, "net_r": -309.2983, "net_usd_at_24_risk": -7423.16, "expectancy_r": -0.45485, "profit_factor": 0.2302, "win_rate_pct": 24.26, "max_drawdown_r": 309.2983, "worst_r": -5.4917, "best_r": 3.5733}. Os sinais arquivados são tratados como dados para auditoria; esse comparativo não valida a causalidade das entradas originais.
Correlação de Spearman entre range anterior e resultado (R), e entre range e magnitude |R|:
```json
{
  "archived_v3": {
    "range_vs_signed_r": -0.011456869061075696,
    "range_vs_absolute_r": 0.23491431111995567,
    "range_winners_mean": 5.187695259740255,
    "range_losers_mean": 5.316221622369882
  },
  "v3_ticks": {
    "range_vs_signed_r": -0.1454691872435745,
    "range_vs_absolute_r": 0.17180983444881892,
    "range_winners_mean": 4.360138624678667,
    "range_losers_mean": 4.594536948148148
  },
  "diagnostic_v4": {
    "range_vs_signed_r": -0.00687563382543679,
    "range_vs_absolute_r": 0.06921523208543086,
    "range_winners_mean": 4.431109123093686,
    "range_losers_mean": 4.320320682102627
  }
}
```

Quartis de volatilidade da V3 arquivada, com limites calculados somente no treino:

| Quartil | N | PF | R líquido | R médio |
|---|---:|---:|---:|---:|
| Q1 | 99 | 1.9313 | 29.33 | 0.29626 |
| Q2 | 174 | 1.8449 | 56.5579 | 0.32505 |
| Q3 | 220 | 1.3782 | 40.1196 | 0.18236 |
| Q4 | 193 | 2.3004 | 129.0896 | 0.66886 |

Limites dos quartis (USD/oz): [3.333504166666626, 4.187291666666681, 5.260510416666693]. Associação descritiva, não causalidade; direção, horário e tendência também variam.

Maiores ganhos e perdas por resultado monetário no snapshot operacional:

| Grupo | Entrada UTC | Resultado original (US$) | R original | Range60 | Spread | R refeito em ticks |
|---|---|---:|---:|---:|---:|---:|
| Ganho | 2026-03-05T15:08:43.010000+00:00 | 215.16 | 8.965 | 9.975 | 1.720 | -1.542 |
| Ganho | 2026-02-04T14:32:48.392000+00:00 | 203.12 | 8.463 | 10.640 | 1.007 | -1.887 |
| Ganho | 2026-03-03T05:48:39.917000+00:00 | 192.80 | 8.033 | 8.118 | 0.930 | -1.792 |
| Ganho | 2026-02-03T06:19:59.552000+00:00 | 187.20 | 7.800 | 16.956 | 1.544 | -2.470 |
| Ganho | 2026-03-19T10:20:25.134000+00:00 | 168.60 | 7.025 | 14.720 | 1.134 | -1.675 |
| Perda | 2026-02-02T05:42:07.727000+00:00 | -87.80 | -3.658 | 34.388 | 2.537 | -3.387 |
| Perda | 2026-02-09T05:30:01.391000+00:00 | -62.80 | -2.617 | 10.874 | 1.130 | -1.475 |
| Perda | 2026-03-31T05:15:00.852000+00:00 | -44.60 | -1.858 | 10.618 | 0.910 | -1.658 |
| Perda | 2026-08-06T15:55:32.725000+00:00 | -38.60 | -1.608 | 7.029 | 0.100 | -1.208 |
| Perda | 2026-02-04T09:33:39.494000+00:00 | -38.12 | -1.588 | 8.823 | 1.100 | -1.875 |

## Limites e reprodução

A reconstrução V3 em ticks usa M30 completos e um candle corrente explícito. O replay/EA antigo tem convenções de janela diferentes. Assim, é uma baseline causal reconstruída, não paridade certificada com o EA. O EA também consulta a API a cada cinco segundos; os gatilhos de 500 ms/2 s exigiriam outra cadência antes de qualquer forward.
A V4 anterior rejeitada permanece arquivada. Este experimento não altera catálogo, flags, execução demo/real ou curvas existentes.
- Historical holdouts were studied previously: out-of-selection, not untouched market evidence.
- Tick V3 reconstructs entries causally; it is not identical to archived candle replay.
- Strict complete M30 buckets, forming candle midpoint, one signal per M5 are explicit replay contracts.
- Stop amendments take effect on next quote; no broker amendment/network latency simulation.
- No swaps, margin rejection, stop-distance limits or lot-step rounding; research only.

```bash
cd /home/codexops/projects/2Lotus/python-service
PYTHONPATH=. .venv/bin/python scripts/research_zigzag_v4_raw_ticks.py --anchor 2026-09-11T20:55:00+00:00 --release 20260911T043125Z-0ef1a31ba0a5 --output data/research/zigzag-v4-raw-20260913-final
PYTHONPATH=. .venv/bin/python scripts/report_zigzag_v4_raw_ticks.py data/research/zigzag-v4-raw-20260913-final
```

Artefatos: `protocol.json`, `report.json`, `diagnostics.json`, `trades.json`, `historical_audit.json`, `analise-interativa.html`. Hashes de todos os arquivos de dados usados e do código estão no relatório/protocolo.
