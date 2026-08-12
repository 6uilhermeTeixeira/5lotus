insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-17',
  'Happy Gold · Impulso Tick 30s',
  'Variante shadow isolada que testa o impulso direcional de 30 segundos reconstruído do forward test.',
  'happy_gold_tick_impulse_shadow',
  E'- Status: pesquisa exploratória permanentemente bloqueada em shadow.\n- Fonte: 30 entradas reconstruídas high/medium e 146 controles pareados do forward test público.\n- Gatilho inicial: movimento absoluto de pelo menos 95,5 pips XAUUSD de 0,01 nos 30 segundos anteriores; alta gera Buy e queda gera Sell.\n- Evidência: AUC 0,859; validação leave-one-day-out com 80,0% de sensibilidade, 82,2% de especificidade e 81,1% de acurácia balanceada.\n- Geometria observada: lote sugerido 0,10, stop de 240 pips e alvo de 1.000 pips.\n- Sessão de pesquisa: 00:00–17:00 UTC para cobrir os horários EET/EEST observados.\n- Persistência: registra candidatos por minuto; paper trade M5 fica desativado porque não representa operações com duração de segundos.\n- Promoção: exige forward test com ticks do broker e gestão/saída tick a tick separada.',
  'XAUUSD',
  'M5',
  true
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
