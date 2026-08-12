insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-20',
  'Happy Gold · Score Tick Multijanela',
  'Reconstrução shadow baseada na assinatura de aceleração observada nas entradas originais.',
  'happy_gold_multiwindow_tick_score_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Evidência: 95 entradas reconstruídas contra 470 controles pareados do mesmo dia.\n- Janelas obrigatórias: movimentos direcionais alinhados em 60, 300 e 900 segundos.\n- Confirmação: score mínimo 4/6 nas janelas 5, 10, 30, 60, 300 e 900 segundos.\n- Validação leave-one-day-out: acurácia balanceada de 75,1% em 60s, 81,8% em 300s e 78,3% em 900s.\n- Gestão: stop virtual 60 pips, breakeven 40/+1, trailing 40/20 e timeout 60 segundos.\n- Promoção: exige replay exaustivo de falsos positivos e forward test independente.',
  'XAUUSD', 'M5', true
)
on conflict (id) do update
set name = excluded.name,
    description = excluded.description,
    strategy_profile = excluded.strategy_profile,
    strategy_description = excluded.strategy_description,
    symbol = excluded.symbol,
    timeframe = excluded.timeframe,
    active = excluded.active;

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
