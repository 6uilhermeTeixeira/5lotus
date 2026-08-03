insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe
)
values (
  'bot-11',
  'Bot 11 — Portfólio 7/6 · 100/75',
  'Variante agressiva em shadow do Bot 8: Bot 7 com 100% e Bot 6 com 75% do risco-base, sem posições simultâneas.',
  'portfolio_6_7_100_75',
  E'- Status: variante agressiva permanentemente bloqueada em shadow.\n- Mercado: somente XAUUSD/M5.\n- Bot 7: 100% do risco-base, mantendo tendência H1/M15, pullback M5 e prioridade sobre conflitos.\n- Bot 6: 75% do risco-base, somente vendas antes de 18 UTC e somente com tendência H1 de baixa confirmada.\n- Os pesos não representam posições simultâneas: uma única exposição é compartilhada pelos componentes.\n- Risco persistido: uma posição, no máximo duas entradas por dia, limite diário de 2R e cooldown de 15 minutos após perda.\n- Validação: risco e drawdown esperados são maiores; exige comparação forward direta com Bots 8 e 10 antes de qualquer promoção.',
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
