alter table public.paper_trades
  add column if not exists partial_close_pct numeric not null default 50,
  add column if not exists expires_at_utc timestamptz;

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
  'bot-7',
  'Bot 7 — Tendência Multitemporal',
  'Experimento em shadow com tendência H1, confirmação M15 e gatilho M5 na sessão de maior estabilidade histórica.',
  'multitimeframe_trend_pullback',
  E'- Status: experimento bloqueado em shadow; os números históricos são exploratórios e exigem forward test independente.\n- Mercado e gráfico: ouro/dólar (XAUUSD) no M5.\n- Tendência longa: MME20 e MME50 de candles H1 completos; exige inclinação a favor e distância mínima de 0,5 ATR(H1).\n- Tendência curta: MME9 e MME21 de candles M15 completos, alinhadas com a direção H1.\n- Gatilho: pullback e rejeição da MME9 no M5, com MME9/MME21 alinhadas.\n- Horário de entrada: 13:00–16:59 UTC, janela ampla escolhida no desenvolvimento histórico; no horário de Brasília corresponde normalmente a 10:00–13:59 (UTC-3).\n- Gestão: no máximo 2 entradas por dia, stop de 1,2 ATR(M5), alvo único de 0,5R e encerramento por tempo após 12 candles (60 minutos).\n- Pesquisa de 365 dias: 73,68% no desenvolvimento, 72,00% na validação e 70,83% no bloco final; custos simulados incluídos.\n- Limitação: a variante foi comparada após a abertura do holdout e não constitui promessa de win rate futuro.',
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
alter table public.paper_trades enable row level security;
revoke all on table public.bots, public.paper_trades from anon, authenticated;
