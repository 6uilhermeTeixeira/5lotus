insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-21',
  'Happy Gold · ZigZag Range Normalizado',
  'Variante shadow do seletor estrutural com filtro de compressão M5 normalizado por ATR.',
  'happy_gold_zigzag_normalized_range_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Base: todos os filtros e a gestão tick do Bot 19.\n- Filtro adicional: range do M5 anterior / ATR14 <= 1,876955.\n- Origem do limiar: percentil 90 das 26 entradas correspondentes de 2025.\n- Holdout 2025 anterior aos rótulos: PF 2,291.\n- Holdout 2026 posterior ao treino: 75 sinais, 57,33% de acerto, PF 2,485, PnL US$ 380,28 e drawdown US$ 34,22.\n- Correspondência original em 2026: 13/14 entradas preservadas.\n- Promoção: exige forward test independente nos ticks da corretora real.',
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
