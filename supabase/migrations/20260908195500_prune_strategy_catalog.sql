-- Keep the public strategy catalog aligned with the ten supported 2Lotus strategies.
insert into public.bots (id, name, description, strategy_profile, symbol, timeframe, active)
values
  ('core-zigzag', 'ZigZag Scalper V1', 'Rompimento de pivôs fractais confirmados em M30.', 'happy_gold_zigzag_scalper', 'XAUUSD', 'M5', true),
  ('core-stochastic', 'Stochastic Sell V1', 'Pullback vendedor com Estocástico 14/3/3 e filtro EMA50.', 'stochastic_sell_session', 'XAUUSD', 'M5', true),
  ('core-multitimeframe', 'Tendência Multitemporal V1', 'Pullback comprador alinhado entre H1, M15 e M5.', 'multitimeframe_trend_pullback', 'XAUUSD', 'M5', true)
on conflict (id) do update set
  name = excluded.name,
  description = excluded.description,
  strategy_profile = excluded.strategy_profile,
  symbol = excluded.symbol,
  timeframe = excluded.timeframe,
  active = excluded.active;

-- Related rows are removed by the existing ON DELETE CASCADE foreign keys.
delete from public.bots
where id not in (
  'core-zigzag', 'core-zigzag-v2', 'core-zigzag-v3',
  'core-stochastic', 'core-stochastic-v2', 'core-stochastic-v3',
  'core-multitimeframe', 'core-multitimeframe-v2', 'core-multitimeframe-v3',
  'core-combined-v3'
);
