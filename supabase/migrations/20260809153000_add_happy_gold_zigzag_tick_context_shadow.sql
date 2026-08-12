insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-18',
  'Happy Gold · ZigZag + Contexto Tick 15m',
  'Variante shadow isolada que combina rompimento ZigZag M30 e contexto direcional de ticks.',
  'happy_gold_zigzag_tick_context_shadow',
  E'- Status: diagnóstico shadow; replay anual rejeitou promoção para execução.\n- Gatilho: rompimento causal de pivô fractal M30 na direção de movimento mínimo de 800 pips XAUUSD durante os 900 segundos anteriores.\n- Evidência retrospectiva: 13 vitórias e 2 perdas entre 15 entradas conhecidas que satisfizeram a combinação.\n- Evidência fora da seleção: 390 sinais no replay de 70.318.713 ticks; melhor cenário com 28,46% de acerto e profit factor 0,946.\n- Geometria observada: lote sugerido 0,10, stop publicado de 240 pips e alvo publicado de 1.000 pips.\n- Persistência: registra candidatos; paper trade M5 fica desativado por não representar operações com duração de segundos.\n- Execução: permanentemente bloqueada por experimental_shadow_lock até nova hipótese causal sobreviver ao replay e ao forward test.',
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
