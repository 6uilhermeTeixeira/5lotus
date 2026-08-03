insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values
  (
    'bot-eur-13',
    'Happy Gold ZigZag · Confirmação de Regime · EUR/USD',
    'Transferência experimental da confirmação seletiva de regime para EUR/USD, sem recalibração e permanentemente bloqueada em shadow.',
    'happy_gold_zigzag_regime_confirmed',
    E'- Status: benchmark cross-market permanentemente bloqueado em shadow.\n- Mercado: EURUSD no M5, usando o histórico canônico de bot-eur-1.\n- Regras preservadas: pivô fractal M30 confirmado, sessão 03:00–19:00 UTC, stop de 240 pontos, alvo de 1.000 pontos, break-even em +40, trailing em +120/60 e saída após dois M5.\n- Confirmação: range e tendência mantêm o rompimento; transição e alta volatilidade exigem fechamento M5 além do pivô e direção H1 alinhada.\n- Escala: ponto de 0,00001; os parâmetros foram transferidos sem calibração específica para EUR/USD.\n- Uso: comparar robustez entre mercados; resultados não autorizam execução real.',
    'EURUSD',
    'M5',
    true
  ),
  (
    'bot-btc-13',
    'Happy Gold ZigZag · Confirmação de Regime · BTC/USD',
    'Transferência experimental da confirmação seletiva de regime para Bitcoin, sem recalibração e permanentemente bloqueada em shadow.',
    'happy_gold_zigzag_regime_confirmed',
    E'- Status: benchmark cross-market permanentemente bloqueado em shadow.\n- Mercado: BTCUSD no M5, com histórico canônico próprio em bot-btc-13.\n- Regras preservadas: pivô fractal M30 confirmado, sessão 03:00–19:00 UTC, stop de 240 pontos, alvo de 1.000 pontos, break-even em +40, trailing em +120/60 e saída após dois M5.\n- Confirmação: range e tendência mantêm o rompimento; transição e alta volatilidade exigem fechamento M5 além do pivô e direção H1 alinhada.\n- Escala inicial: ponto de 0,01; os parâmetros foram transferidos sem calibração específica para Bitcoin.\n- Uso: comparar robustez entre mercados; resultados não autorizam execução real.',
    'BTCUSD',
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
