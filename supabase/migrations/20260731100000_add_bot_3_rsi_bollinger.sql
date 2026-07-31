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
  'bot-3',
  'Bot 3 — RSI Bollinger',
  'Estratégia contrária de reversão à média com RSI e Bandas de Bollinger.',
  'rsi_bollinger_reversion',
  E'- Mercado e gráfico: XAUUSD no M5, executado em paralelo aos Bots 1 e 2.\n- Contexto: Bandas de Bollinger de 20 períodos e 2 desvios identificam afastamentos da média.\n- Gatilho de compra: mínima toca ou rompe a banda inferior, o candle fecha novamente dentro da banda e o RSI(14) está até 45.\n- Gatilho de venda: máxima toca ou rompe a banda superior, o candle fecha novamente dentro da banda e o RSI(14) está a partir de 55.\n- Stop: extremo do candle de rejeição com buffer de 0,25 ATR(14).\n- Gestão: parcial na média de 20 períodos, breakeven e alvo final em 2R.\n- Fluxo: não bloqueia esta estratégia, mantendo a comparação independente.\n- Validação: roda somente em shadow e registra paper trades antes de qualquer avaliação para execução real.',
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
