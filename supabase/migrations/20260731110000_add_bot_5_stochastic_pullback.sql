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
  'bot-5',
  'Bot 5 — Stochastic Pullback',
  'Estratégia de continuação de tendência após correção usando Estocástico e MME50.',
  'stochastic_trend_pullback',
  E'- Mercado e gráfico: XAUUSD no M5, executado em paralelo aos Bots 1, 2, 3 e 4.\n- Contexto: a MME50 define a tendência e o Estocástico lento (14,3,3) mede a correção.\n- Gatilho de compra: preço acima da MME50 e linha %K cruza acima da %D após região até 35.\n- Gatilho de venda: preço abaixo da MME50 e linha %K cruza abaixo da %D após região a partir de 65.\n- Stop: extremo dos últimos 3 candles com buffer de 0,25 ATR(14).\n- Gestão: parcial de 50% em 1R, breakeven no saldo e alvo final em 2R.\n- Fluxo: não bloqueia esta estratégia, preservando uma amostra independente.\n- Validação: roda em shadow e registra paper trades próprios antes de qualquer avaliação para execução real.',
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
