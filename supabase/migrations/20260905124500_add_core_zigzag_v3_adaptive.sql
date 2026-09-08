insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'core-zigzag-v3',
  'ZigZag Scalper V3 · Regime Adaptativo',
  'Alterna causalmente entre o V1 em volatilidade normal e o V2 estrutural durante expansões do range M5.',
  'zigzag_scalper_v3_adaptive_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Calcula o range médio dos últimos 60 candles M5 completos, sem usar dados futuros.\n- Abaixo de 6,00 no XAUUSD, usa a lógica e a geometria do ZigZag Scalper V1.\n- Em 6,00 ou mais, usa os filtros estruturais e de ticks do V2.\n- Mantém risco monetário aproximado de US$ 24 por operação: 0,10 lote no modo V1 e 0,40 no modo V2.\n- Seleção 2025: 271 operações, US$ 2.334,80 e PF 2,015.\n- Holdout jan-abr/2026: 208 operações, US$ 1.859,54 e PF 1,678.\n- Holdout mai-ago/2026: 253 operações, US$ 1.442,97 e PF 1,507.\n- Promoção exige forward test independente com ticks da corretora.',
  'XAUUSD',
  'M5',
  true
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
