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
  'bot-4',
  'Bot 4 — MACD Trend',
  'Estratégia de tendência por cruzamento MACD com filtro de MME50.',
  'macd_trend_crossover',
  E'- Mercado e gráfico: XAUUSD no M5, executado em paralelo aos Bots 1, 2 e 3.\n- Contexto: o MACD(12,26,9) mede mudança de momentum e a MME50 define a direção principal.\n- Gatilho de compra: linha MACD cruza acima da linha de sinal com fechamento acima da MME50.\n- Gatilho de venda: linha MACD cruza abaixo da linha de sinal com fechamento abaixo da MME50.\n- Stop: distância de 1 ATR(14) a partir da entrada.\n- Gestão: parcial de 50% em 1R, breakeven no saldo e alvo final em 2R.\n- Fluxo: não bloqueia esta estratégia, preservando uma amostra independente.\n- Validação: roda em shadow e registra paper trades próprios antes de qualquer avaliação para execução real.',
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
