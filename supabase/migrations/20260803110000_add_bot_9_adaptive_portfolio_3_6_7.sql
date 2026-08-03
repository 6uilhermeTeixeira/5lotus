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
  'bot-9',
  'Bot 9 — Seletor Adaptativo 3/6/7',
  'Candidato experimental em shadow que seleciona diariamente Bot 7, Bot 6 ou Bot 3 filtrado usando somente os 120 dias anteriores.',
  'adaptive_portfolio_3_6_7',
  E'- Status: candidato adaptativo permanentemente bloqueado em shadow; exige replay integrado e forward test antes de qualquer execução.\n- Mercado e gráfico: somente XAUUSD no M5.\n- Seletor causal: no início de cada dia UTC, escolhe o componente elegível com maior expectativa nos 120 dias anteriores; nunca usa operações do próprio dia.\n- Saúde mínima: pelo menos 8 operações encerradas, expectativa positiva e profit factor igual ou superior a 1,10. Se nenhum componente passar, não opera.\n- Bot 7: núcleo de tendência multitemporal, com seu regime interno H1/M15.\n- Bot 6: somente vendas antes de 18 UTC e apenas quando o regime externo confirma tendência de baixa.\n- Bot 3: somente range com ADX baixo e percentil de ATR igual ou superior a 25.\n- Exposição compartilhada: somente o componente selecionado pode sinalizar; no máximo uma posição em XAUUSD, duas entradas por dia e limite diário de 2R.\n- Risco: o componente selecionado recebe 100% do risco-base do candidato; não há soma de risco entre estratégias.\n- Validação: seleção congelada por dia, custos integrados e nenhuma recalibração com o próprio dia.',
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
