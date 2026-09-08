insert into public.bots (
  id, name, subtitle, description, strategy_profile, strategy_description,
  symbol, timeframe, results_file, active
) values (
  'core-zigzag-v4',
  'ZigZag Scalper V4',
  'Microestrutura de Ticks',
  'Filtra rompimentos ZigZag causais por persistência, eficiência e aceleração da microestrutura nos segundos anteriores à entrada.',
  'zigzag_scalper_v4_tick_microstructure_shadow',
  E'- Mantém o rompimento causal dos pivôs M30 da V1.\n- Exige impulso direcional crescente nas janelas de 5, 30 e 60 segundos.\n- Mede eficiência do caminho e aceleração da atividade nos agregados de 1 segundo.\n- Usa stop inicial de 120 pips, alvo de 600 pips, lote de pesquisa 0,20 e ciclo máximo de 60 segundos.\n- O replay tick walk-forward rejeitou a hipótese por expectativa negativa e baixa correspondência com as entradas originais.\n- Permanece exclusivamente em shadow, com execução permanentemente bloqueada, para auditoria e novas pesquisas.',
  'XAUUSD',
  'M5',
  'results/core-zigzag-v4.json',
  true
)
on conflict (id) do update set
  name = excluded.name,
  subtitle = excluded.subtitle,
  description = excluded.description,
  strategy_profile = excluded.strategy_profile,
  strategy_description = excluded.strategy_description,
  symbol = excluded.symbol,
  timeframe = excluded.timeframe,
  results_file = excluded.results_file,
  active = excluded.active,
  updated_at = now();
