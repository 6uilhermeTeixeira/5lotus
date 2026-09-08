insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'core-multitimeframe-v2',
  'Tendência Multitemporal V2 · Impulso 1,25R',
  'Variante shadow com força H1 mínima de 0,5 ATR, alvo de 1,25R e duração máxima de 30 minutos.',
  'multitimeframe_trend_pullback_v2_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Mantém EMA20/EMA50 no H1, EMA9/EMA21 no M15 e pullback sobre EMA9 no M5.\n- Reduz a força H1 mínima de 0,7 para 0,5 ATR.\n- Opera somente compras entre 13:00 e 15:59 UTC.\n- Usa stop de 1,2 ATR, alvo único de 1,25R e duração máxima de 6 candles M5.\n- Mantém 50% do risco-base.\n- Replay de pesquisa: 114 operações, PF 1,68, expectativa de 0,224R e drawdown de 5,37R.\n- Promoção exige forward test independente.',
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
