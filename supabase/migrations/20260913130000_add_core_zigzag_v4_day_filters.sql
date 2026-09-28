insert into public.bots (
  id, name, subtitle, description, strategy_profile, strategy_description,
  symbol, timeframe, results_file, active
) values (
  'core-zigzag-v4', 'ZigZag Scalper V4', 'Dia, Horário e Direção',
  'Preserva o rompimento causal M30 da V1 e aplica filtros estáticos de dia, horário UTC e direção.',
  'zigzag_scalper_v4_day_filters_shadow',
  E'- Segunda: compra, 04:00-13:59 UTC.\n- Terça: compra, 03:00-09:59 UTC.\n- Quarta: compra, 03:00-18:59 UTC.\n- Quinta: ambas as direções, 03:00-11:59 UTC.\n- Sexta: venda, 03:00-11:59 UTC.\n- Mantém stop de 240 pontos, alvo de 1000 pontos e limite de 2 candles M5 da V1.\n- Shadow; requer validação forward independente.',
  'XAUUSD', 'M5', 'results/core-zigzag-v4.json', true
)
on conflict (id) do update set
  name = excluded.name,
  subtitle = excluded.subtitle,
  description = excluded.description,
  strategy_profile = excluded.strategy_profile,
  strategy_description = excluded.strategy_description,
  symbol = excluded.symbol,
  timeframe = excluded.timeframe,
  results_file = excluded.results_file,
  active = excluded.active,
  updated_at = now();
