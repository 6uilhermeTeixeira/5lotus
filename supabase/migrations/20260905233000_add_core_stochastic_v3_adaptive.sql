insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'core-stochastic-v3',
  'Stochastic Sell V3 · Regime Adaptativo',
  'Regime adaptativo que preserva a geometria da V2 nos contextos H1 robustos e evita os regimes e horários fracos identificados nas V1/V2.',
  'stochastic_sell_v3_adaptive_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Mantém da V2 o extremo 85, parcial de 50% em 1R e alvo final de 1,25R.\n- Opera antes das 13:00 UTC e usa regime H1 causal.\n- Bloqueia tendência H1 vendedora, regime em que a V2 apresentou PF 0,68.\n- Replay atual: 44 operações, 70,45% de acerto, PF 2,52, expectativa de 0,412R e drawdown de 1,98R.\n- Promoção exige forward test independente.',
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
