-- Aprovado pelo responsável: resultados e candles anteriores do bot-1 são descartados.
delete from public.market_candles where bot_id = 'bot-1';
delete from public.trade_results where bot_id = 'bot-1';

update public.bots
set name = 'Bot 1 — Fimath',
    description = 'Estratégia Fimath com MME20 e confirmação obrigatória de fluxo.',
    strategy_profile = 'fimath_ema20_flow',
    strategy_description = E'- Mercado e gráfico: XAUUSD no M5.\n- Viés: fechamento e inclinação da MME20 definem compras ou vendas.\n- Gatilhos: pullback/rejeição na MME20 ou padrão fora-dentro após extensão de preço.\n- Fluxo obrigatório: agressão ou absorção inferidas do livro e dos ticks, normalizadas contra os últimos 5 minutos.\n- Stop: estrutura de rejeição com buffer adaptativo de ATR(14).\n- Gestão: risco de 1%, parcial de 50% em 1R, breakeven no saldo e alvo final em 2R.\n- Validação: opera em shadow até registrar 30 paper trades completos.'
where id = 'bot-1';

create table if not exists public.strategy_signals (
  signal_key text primary key,
  bot_id text not null references public.bots(id) on delete cascade,
  created_at timestamptz not null default timezone('utc', now()),
  payload jsonb not null,
  response jsonb not null
);

create table if not exists public.paper_trades (
  signal_key text primary key references public.strategy_signals(signal_key) on delete cascade,
  bot_id text not null references public.bots(id) on delete cascade,
  side text not null check (side in ('buy','sell')),
  entry_price numeric not null, initial_stop_price numeric not null, stop_price numeric not null,
  partial_price numeric not null, target_price numeric not null,
  partial_hit boolean not null default false, status text not null default 'open',
  outcome_r numeric, opened_at_utc timestamptz not null, closed_at_utc timestamptz
);

alter table public.strategy_signals enable row level security;
alter table public.paper_trades enable row level security;
revoke all on table public.strategy_signals, public.paper_trades from anon, authenticated;
