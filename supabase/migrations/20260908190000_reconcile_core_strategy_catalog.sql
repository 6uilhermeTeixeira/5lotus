-- Keep the production catalog aligned with python-service/data/bots.json.
-- The EA still polls only the explicitly configured V3 execution profiles;
-- active here means visible/testable in the research dashboard.
insert into public.bots (
  id, name, subtitle, description, strategy_profile, strategy_description,
  symbol, timeframe, results_file, active
) values
  ('core-zigzag', 'ZigZag Scalper V1', '',
   'Rompimento de pivôs fractais confirmados em M30, executado e monitorado pelo fluxo M5.',
   'happy_gold_zigzag_scalper', 'Estratégia-base ZigZag causal M30.',
   'XAUUSD', 'M5', 'results/core-zigzag.json', true),
  ('core-stochastic', 'Stochastic Sell V1', 'Sessão 18 UTC',
   'Pullback vendedor com Estocástico 14/3/3, filtro EMA50 e corte de entrada às 18:00 UTC.',
   'stochastic_sell_session', 'Estratégia-base Stochastic Sell.',
   'XAUUSD', 'M5', 'results/core-stochastic.json', true),
  ('core-multitimeframe', 'Tendência Multitemporal V1', '',
   'Pullback comprador alinhado entre H1, M15 e M5 durante a janela 13:00-16:00 UTC.',
   'multitimeframe_trend_pullback', 'Estratégia-base de tendência multitemporal.',
   'XAUUSD', 'M5', 'results/core-multitimeframe.json', true),
  ('core-portfolio', 'Portfólio Combinado V1', 'Coordenação 7/6 · 100/100',
   'Coordenador que prioriza ZigZag confirmado e combina Tendência Multitemporal com Stochastic Sell.',
   'happy_gold_portfolio_100_100', 'Portfólio-base das três famílias.',
   'XAUUSD', 'M5', 'results/core-portfolio.json', true)
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

update public.bots
set active = id in (
  'core-zigzag', 'core-zigzag-v2', 'core-zigzag-v3', 'core-zigzag-v4',
  'core-stochastic', 'core-stochastic-v2', 'core-stochastic-v3',
  'core-multitimeframe', 'core-multitimeframe-v2', 'core-multitimeframe-v3',
  'core-portfolio', 'core-combined-v3'
)
where id like 'core-%';
