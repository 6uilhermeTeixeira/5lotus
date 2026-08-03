insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-13',
  'Happy Gold ZigZag · Confirmação de Regime',
  'Variante paralela do ZigZag que confirma rompimentos somente nos regimes ambíguos, permanentemente bloqueada em shadow.',
  'happy_gold_zigzag_regime_confirmed',
  E'- Status: variante experimental do Happy Gold, permanentemente bloqueada em shadow.\n- Base preservada: pivô fractal M30 confirmado, sessão 03:00–19:00 UTC, lote 0,10, stop de 240 pontos e alvo de 1.000 pontos.\n- Gestão preservada: break-even em +40 pontos, trailing após +120 pontos com distância de 60 e saída máxima após dois candles M5.\n- Range e tendência: mantém o rompimento original do Bot 12.\n- Transição e alta volatilidade: exige fechamento M5 além do pivô e direção H1 alinhada ao sinal.\n- Replay integrado de 365 dias: 610 operações, PnL US$ 2.655,40, PF 1,39, expectativa 0,181R e drawdown máximo 15,66R.\n- Janeiro–março de 2026: aproximadamente +US$ 540 no replay, contra período negativo da base.\n- Limitação: não dominou a base em todos os meses; requer validação forward com ticks e permanece apenas como candidato paralelo.',
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
