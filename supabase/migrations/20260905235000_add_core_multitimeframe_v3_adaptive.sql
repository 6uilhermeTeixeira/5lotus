insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'core-multitimeframe-v3',
  'Tendência Multitemporal V3 · Regime Adaptativo',
  'Alterna causalmente entre as geometrias V1 e V2 conforme o regime H1 e evita tendências contrárias.',
  'multitimeframe_trend_pullback_v3_adaptive_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Range/transição H1 usa V2 (0,5 ATR, 1,25R, 6 candles).\n- Tendência compradora/alta volatilidade não contrária usa V1 (0,7 ATR, 0,75R, 12 candles).\n- Bloqueia tendência H1 vendedora e histórico insuficiente.\n- Replay atual: 107 operações, 66,36% de acerto, PF 1,77, expectativa de 0,240R e drawdown de 4,52R.\n- Promoção exige forward test independente.',
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
