insert into public.bots (
  id,
  name,
  description,
  strategy_profile,
  strategy_description,
  symbol,
  timeframe
)
values (
  'bot-2',
  'Bot 2 — Momentum ATR',
  'Estratégia paralela de rompimento com tendência e volatilidade adaptativa.',
  'momentum_atr_breakout',
  E'- Mercado e gráfico: XAUUSD no M5, em paralelo ao Bot 1.\n- Tendência: alinhamento das MME20 e MME50, com inclinação da MME20 na direção da entrada.\n- Gatilho: fechamento rompe a máxima ou mínima dos 12 candles anteriores.\n- Stop: distância adaptativa de 1,2 ATR(14).\n- Gestão: risco de 1%, parcial de 50% em 1R, breakeven no saldo e alvo final em 2R.\n- Fluxo: não bloqueia esta estratégia, criando uma comparação independente com o Fimath.\n- Validação: roda somente em shadow e registra paper trades antes de qualquer avaliação para execução real.',
  'XAUUSD',
  'M5'
)
on conflict (id) do update
set name = excluded.name,
    description = excluded.description,
    strategy_profile = excluded.strategy_profile,
    strategy_description = excluded.strategy_description,
    symbol = excluded.symbol,
    timeframe = excluded.timeframe;

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
