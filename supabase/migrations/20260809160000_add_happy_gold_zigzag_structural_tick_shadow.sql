insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-19',
  'Happy Gold · Seletor Estrutural Tick',
  'Hipótese shadow seletiva para rompimentos ZigZag com tendência M5 e contexto de ticks.',
  'happy_gold_zigzag_structural_tick_shadow',
  E'- Status: candidato shadow de amostra pequena; execução permanentemente bloqueada.\n- Gatilho: rompimento causal ZigZag M30, exceto sexta-feira.\n- Contexto tick: movimento alinhado mínimo de 1.000 pips nos 900 segundos anteriores.\n- Estrutura M5: distância direcional da EMA20 mínima de 900 pips e extensão máxima de 50 pips além do pivô.\n- Replay: 27 sinais no ano; 48,15% de acerto e profit factor 2,653 com stop virtual de 60 pips e saída máxima em 30 segundos.\n- Gestão shadow selecionada: stop 60 pips, breakeven em 40 com trava +1, trailing 40/20 e máximo 60 segundos; 66,67% de acerto e profit factor 3,092.\n- Holdout anterior ao período rotulado: 14 sinais, 42,86% de acerto e profit factor 1,782.\n- Robustez: positivo em 8 de 10 gestões; stop de 30 pips foi instável.\n- Promoção: exige forward test em ticks do broker e nova amostra temporal.',
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
