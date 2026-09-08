insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'core-stochastic-v2',
  'Stochastic Sell V2 · Extremo 85',
  'Variante seletiva sem veto H1: sobrecompra extrema, corte às 15:00 UTC e alvo final de 1,25R.',
  'stochastic_sell_v2_shadow',
  E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Exige preço abaixo da EMA50 no M5 e cruzamento baixista do Estocástico 14/3/3.\n- Exige que %K ou %D estivesse em 85 ou mais antes do cruzamento.\n- Aceita somente vendas e bloqueia novas entradas às 15:00 UTC ou depois.\n- Usa a EMA50 como filtro causal interno e não aplica o veto genérico de regime H1.\n- Posiciona o stop acima das últimas 3 velas acrescido de 0,25 ATR.\n- Realiza parcial de 50% em 1R e mantém alvo final em 1,25R.\n- Replay de pesquisa: 74 operações, PF 1,58, expectativa de 0,206R e drawdown de 3,89R.\n- Promoção exige forward test independente.',
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
