insert into public.bots (
  id, name, subtitle, description, strategy_profile, strategy_description,
  symbol, timeframe, results_file, active
) values (
  'core-zigzag-v6', 'ZigZag Scalper V6', 'V5 + Direção Stochastic V3',
  'Mantém a V5 e permite vendas apenas quando o contexto causal da Stochastic V3 está favorável.',
  'zigzag_scalper_v6_stochastic_sell_gate_shadow',
  E'- Compras idênticas à V5.\n- Vendas apenas antes de 13:00 UTC, com regime H1 não-vendedor e fechamento M5 abaixo da EMA50.\n- O cruzamento estocástico não é obrigatório: o filtro é de contexto e não cria entradas.\n- Shadow até walk-forward e validação Fusion.',
  'XAUUSD', 'M5', 'results/core-zigzag-v6.json', true
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
