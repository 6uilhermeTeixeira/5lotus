insert into public.bots (
  id, name, subtitle, description, strategy_profile, strategy_description,
  symbol, timeframe, results_file, active
) values (
  'core-zigzag-v5', 'ZigZag Scalper V5', 'V1/V2 + Gate V4 Adaptativo',
  'Seleciona V1 ou V2 pelo regime causal e usa o filtro V4 apenas para bloquear sinais de transição de menor qualidade.',
  'zigzag_scalper_v5_adaptive_gate_shadow',
  E'- Range médio dos últimos 60 candles M5 completos abaixo de 4,50: V1.\n- Entre 4,50 e 6,00: V1 com gate V4 de dia, hora e direção.\n- Em 6,00 ou mais: V2 estrutural com confirmação de ticks.\n- O gate V4 apenas bloqueia sinais; nunca cria entradas.\n- Shadow até walk-forward e validação com ticks Fusion.',
  'XAUUSD', 'M5', 'results/core-zigzag-v5.json', true
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
