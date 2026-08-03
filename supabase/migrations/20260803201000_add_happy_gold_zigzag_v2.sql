alter table public.paper_trades
  add column if not exists point_size numeric,
  add column if not exists break_even_trigger_points numeric,
  add column if not exists break_even_offset_points numeric,
  add column if not exists trailing_activation_points numeric,
  add column if not exists trailing_distance_points numeric;

insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-15',
  'Happy Gold ZigZag · Reteste ATR',
  'Happy Gold v2: rompimento M30, reteste M5, regime direcional e gestão proporcional à volatilidade, permanentemente em shadow.',
  'happy_gold_zigzag_retest_atr',
  E'- Status: candidata experimental permanentemente bloqueada em shadow e rejeitada para seleção.\n- Entrada: pivô fractal M30 confirmado, fechamento M5 além do nível e posterior reteste com rejeição direcional.\n- Regime: somente tendência H1 alinhada; ATR entre os percentis 10 e 90 e sessão 07:00–16:00 UTC.\n- Extensão: entrada no máximo 0,35 ATR(M5) distante do pivô.\n- Stop: maior entre 1,5 ATR(M5) e a estrutura do reteste com margem de 0,2 ATR.\n- Gestão: alvo 2R, break-even em 0,8R, trailing após 1,2R com distância de 0,8 ATR e encerramento após 12 candles M5.\n- Risco: uma posição por símbolo e tamanho calculado pelo risco configurado.\n- Replay anual: 22 trades, US$ 70,10, PF 1,32, expectativa +0,1285R, drawdown 3,63R e somente 5/10 janelas positivas.\n- Validação: falhou estabilidade temporal; permanece apenas para análise gráfica e forward test em shadow.',
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
alter table public.paper_trades enable row level security;
revoke all on table public.bots, public.paper_trades from anon, authenticated;
