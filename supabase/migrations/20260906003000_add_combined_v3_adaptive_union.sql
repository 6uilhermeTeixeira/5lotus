insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'core-combined-v3',
  'Combinação das 3 V3 · Regime Adaptativo',
  'Portfólio paralelo das três V3, com posições simultâneas e risco independente de 1% em cada estratégia.',
  'portfolio_v3_adaptive_union_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Mantém três trilhas independentes e permite até três posições simultâneas.\n- Cada V3 arrisca 1% do patrimônio; exposição simultânea máxima teórica de 3%.\n- Não há prioridade, conflito ou substituição entre os sinais.\n- Replay paralelo composto: 887 operações, US$ 132.358,67, PF 1,64, expectativa 0,311R e drawdown 13,28R.\n- Exige forward test independente com ticks da corretora.',
  'XAUUSD', 'M5', true
)
on conflict (id) do update
set name = excluded.name,
    description = excluded.description,
    strategy_profile = excluded.strategy_profile,
    strategy_description = excluded.strategy_description,
    symbol = excluded.symbol,
    timeframe = excluded.timeframe,
    active = excluded.active;

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
