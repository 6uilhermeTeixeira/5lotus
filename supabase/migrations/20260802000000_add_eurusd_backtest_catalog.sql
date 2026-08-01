create table if not exists public.backtest_snapshots (
  bot_id text not null references public.bots(id) on delete cascade,
  period_days integer not null check (period_days between 1 and 3650),
  period_start_utc timestamptz not null,
  period_end_utc timestamptz not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  primary key (bot_id, period_days)
);

create index if not exists backtest_snapshots_period_idx
  on public.backtest_snapshots (period_days, updated_at desc);

drop trigger if exists set_backtest_snapshots_updated_at on public.backtest_snapshots;
create trigger set_backtest_snapshots_updated_at
before update on public.backtest_snapshots
for each row execute function public.set_2lotus_updated_at();

alter table public.backtest_snapshots enable row level security;
revoke all on table public.backtest_snapshots from anon, authenticated;

with mapping(new_id, source_id, eur_name) as (
  values
    ('bot-eur-1', 'bot-1', 'Bot 1 — Fimath · EUR/USD'),
    ('bot-eur-2', 'bot-2', 'Bot 2 — Momentum ATR · EUR/USD'),
    ('bot-eur-3', 'bot-3', 'Bot 3 — RSI Bollinger · EUR/USD'),
    ('bot-eur-4', 'bot-4', 'Bot 4 — MACD Trend · EUR/USD'),
    ('bot-eur-5', 'bot-5', 'Bot 5 — Stochastic Pullback · EUR/USD'),
    ('bot-eur-6', 'bot-6', 'Bot 6 — Stochastic Sell 18 UTC · EUR/USD'),
    ('bot-eur-7', 'bot-7', 'Bot 7 — Tendência Multitemporal · EUR/USD')
)
insert into public.bots (id, name, description, strategy_profile, strategy_description, symbol, timeframe)
select
  mapping.new_id,
  mapping.eur_name,
  'Aplicação em EUR/USD das mesmas regras usadas no XAU/USD, sem recalibração específica para o novo ativo.',
  source.strategy_profile,
  replace(replace(source.strategy_description, 'XAUUSD', 'EURUSD'), 'ouro/dólar', 'euro/dólar')
    || E'\n- Comparabilidade: parâmetros, filtros e horários foram preservados para medir a capacidade de generalização fora do XAU/USD.',
  'EURUSD',
  source.timeframe
from mapping
join public.bots source on source.id = mapping.source_id
on conflict (id) do update
set name = excluded.name,
    description = excluded.description,
    strategy_profile = excluded.strategy_profile,
    strategy_description = excluded.strategy_description,
    symbol = excluded.symbol,
    timeframe = excluded.timeframe;
