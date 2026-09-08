insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'core-zigzag-v2',
  'ZigZag Scalper V2 · Tick + Range',
  'Rompimento ZigZag M30 filtrado por estrutura M5, impulso de ticks e compressão normalizada por ATR.',
  'happy_gold_zigzag_normalized_range_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Mantém os pivôs causais M30 da ZigZag Scalper original.\n- Exige impulso direcional de 900 segundos >= 1.000 pips e distância direcional da EMA20 >= 900 pips.\n- Aceita extensão máxima de 50 pips além do pivô e exclui sextas-feiras.\n- Exige range do M5 anterior / ATR14 <= 1,876955192 e spread máximo de 15 pontos.\n- Usa stop de 60 pips, breakeven em 40/+1, trailing 40/20 e tempo máximo de 60 segundos.\n- Holdout 2026: 57,33% de acerto, PF 2,485 e drawdown 34,22; holdout posterior: 51,28%, PF 1,613.\n- Promoção exige forward test independente com ticks da corretora.',
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
