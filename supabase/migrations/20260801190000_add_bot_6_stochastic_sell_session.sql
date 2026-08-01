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
  'bot-6',
  'Bot 6 — Stochastic Sell 18 UTC',
  'Variante experimental isolada do Stochastic: somente vendas e entradas antes das 18h UTC.',
  'stochastic_sell_session',
  E'- Experimento: variante isolada do Bot 5; não altera a estratégia original.\n- Mercado e gráfico: XAUUSD no M5.\n- Contexto técnico: MME50 e Estocástico lento (14,3,3), com o mesmo gatilho do Stochastic Pullback.\n- Direção: somente vendas; candidatos de compra são observados, mas bloqueados antes de virar sinal.\n- Horário de entrada: 06:00 até 17:59 UTC; posições podem permanecer abertas até o encerramento padrão das 21:00 UTC.\n- Stop e gestão: extremo dos últimos 3 candles com buffer de 0,25 ATR(14), parcial de 50% em 1R, breakeven e alvo final em 2R.\n- Origem da hipótese: melhor estabilidade anual observada nas vendas e deterioração das entradas após 18h UTC.\n- Validação: exclusivamente shadow/paper; qualquer promoção exige validação temporal e forward test independente.',
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
