insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe
)
values (
  'bot-10',
  'Bot 10 — Portfólio 7/6 · 75/50',
  'Variante paralela em shadow do Bot 8: Bot 7 com 75% e Bot 6 com 50% do risco-base, sem posições simultâneas.',
  'portfolio_6_7_75_50',
  E'- Status: variante paralela permanentemente bloqueada em shadow.\n- Mercado: somente XAUUSD/M5.\n- Bot 7: 75% do risco-base, mantendo tendência H1/M15, pullback M5 e prioridade sobre conflitos.\n- Bot 6: 50% do risco-base, somente vendas antes de 18 UTC e somente com tendência H1 de baixa confirmada.\n- Os pesos não somam uma carteira simultânea: apenas um componente pode ocupar a exposição compartilhada.\n- Risco persistido: uma posição, no máximo duas entradas por dia, limite diário de 2R e cooldown de 15 minutos após perda.\n- Validação: deve rodar em paralelo com o Bot 8 durante forward test antes de qualquer promoção.',
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
