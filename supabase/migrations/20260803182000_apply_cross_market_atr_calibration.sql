update public.bots
set description = 'Calibração ATR/R da confirmação seletiva de regime para EUR/USD, rejeitada na confirmação anual e mantida somente em shadow.',
    strategy_description = E'- Status: calibração cross-market rejeitada e permanentemente bloqueada em shadow.\n- Mercado: EURUSD no M5, usando o histórico canônico de bot-eur-1.\n- Entrada: pivô fractal M30 span 2 e a mesma confirmação seletiva de regime do Bot 13.\n- Geometria: stop de 1,5 ATR(M30), alvo de 2,5R, break-even em 1R, trailing após 1,2R com distância de 1 ATR.\n- Sessão e tempo: 07:00–17:00 UTC e saída máxima após 12 candles M5.\n- Confirmação anual: 379 operações, 41,69% de acerto, PnL padronizado de -US$ 457,27, PF 0,73, expectativa de -0,1018R e drawdown de 44,03R.\n- Comparação: melhorou o PF do baseline 0,36, mas falhou expectativa, PF e estabilidade temporal; não autoriza execução real.'
where id = 'bot-eur-13';

update public.bots
set description = 'Calibração ATR/R da confirmação seletiva de regime para Bitcoin, rejeitada na confirmação anual e mantida somente em shadow.',
    strategy_description = E'- Status: calibração cross-market rejeitada e permanentemente bloqueada em shadow.\n- Mercado: BTCUSD no M5 com candles spot BTC-USD da Coinbase Exchange.\n- Entrada: pivô fractal M30 span 3 e a mesma confirmação seletiva de regime do Bot 13.\n- Geometria: stop de 1,5 ATR(M30), alvo de 2,5R, break-even em 1R, trailing após 1,2R com distância de 1 ATR.\n- Sessão e tempo: 12:00–23:59 UTC e saída máxima após 8 candles M5.\n- Confirmação anual: 301 operações, 50,83% de acerto, PnL padronizado de US$ 15.740,61, PF 1,04, expectativa de 0,0473R e drawdown de 12,08R.\n- Comparação: melhorou o PF do baseline 0,32, mas falhou PF mínimo e estabilidade temporal; não autoriza execução real.'
where id = 'bot-btc-13';

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
