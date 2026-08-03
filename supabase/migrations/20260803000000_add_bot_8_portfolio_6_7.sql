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
  'bot-8',
  'Bot 8 — Portfólio Tendência + Stochastic',
  'Portfólio experimental em shadow: Bot 7 como núcleo com 75% do risco e Bot 6 como complemento com 25%, sob exposição e perda diária compartilhadas.',
  'portfolio_6_7',
  E'- Status: portfólio integrado bloqueado em shadow; exige replay integrado e forward test antes de qualquer execução.\n- Mercado e gráfico: XAUUSD no M5.\n- Componente principal: regras do Bot 7 Tendência Multitemporal, somente comprado, com 75% do risco-base do portfólio.\n- Componente complementar: regras do Bot 6 Stochastic Sell 18 UTC, somente vendido, com 25% do risco-base do portfólio.\n- Prioridade: se ambos confirmarem no mesmo candle, o Bot 7 prevalece.\n- Exposição compartilhada: no máximo uma posição em XAUUSD; sinais opostos ou adicionais são bloqueados enquanto houver posição aberta.\n- Risco compartilhado: no máximo 2 entradas por dia e limite diário de 2R no replay integrado.\n- Custos e validação: spread, slippage e comissão configurável devem ser aplicados ao conjunto; pesos não serão recalibrados com o mesmo histórico.',
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
