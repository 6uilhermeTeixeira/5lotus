update public.bots
set strategy_description = strategy_description
  || E'\n- Replay inicial de 365 dias: 669 operações, 26,91% de acerto, PnL padronizado de -US$ 972,90, PF 0,36, expectativa de -0,0606R e drawdown de 40,79R; transferência rejeitada.'
where id = 'bot-eur-13';

update public.bots
set strategy_description = strategy_description
  || E'\n- Replay inicial de 365 dias: 606 operações, 7,43% de acerto, PnL padronizado de -US$ 9.365,40 e PF 0,32; transferência rejeitada.'
where id = 'bot-btc-13';

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
