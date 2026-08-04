create table if not exists public.market_history (
  symbol text not null,
  timeframe text not null,
  timestamp_utc timestamptz not null,
  open numeric not null,
  high numeric not null,
  low numeric not null,
  close numeric not null,
  volume numeric not null default 0,
  source text not null default 'mt5',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  primary key (symbol, timeframe, timestamp_utc)
);

insert into public.market_history (symbol, timeframe, timestamp_utc, open, high, low, close, volume, source, created_at, updated_at)
select distinct on (symbol, timeframe, timestamp_utc)
  symbol, timeframe, timestamp_utc, open, high, low, close, volume,
  case when bot_id = 'bot-1' then 'mt5-canonical' else 'mt5' end,
  created_at, updated_at
from public.market_candles
order by symbol, timeframe, timestamp_utc,
  case when bot_id = 'bot-1' then 0 when bot_id = 'bot-eur-1' then 1 else 2 end,
  updated_at desc
on conflict (symbol, timeframe, timestamp_utc) do update
set open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume,
    source = excluded.source,
    updated_at = excluded.updated_at;

create index if not exists market_history_latest_idx
  on public.market_history (symbol, timeframe, timestamp_utc desc);

drop trigger if exists set_market_history_updated_at on public.market_history;
create trigger set_market_history_updated_at
before update on public.market_history
for each row execute function public.set_2lotus_updated_at();

create table if not exists public.bot_runtime_status (
  bot_id text primary key references public.bots(id) on delete cascade,
  last_request_at_utc timestamptz,
  last_candle_at_utc timestamptz,
  last_action text,
  last_reason text,
  last_latency_ms numeric,
  consecutive_errors integer not null default 0,
  last_error text,
  updated_at timestamptz not null default timezone('utc', now())
);

alter table public.backtest_snapshots
  add column if not exists strategy_version text not null default 'legacy',
  add column if not exists settings_fingerprint text not null default 'legacy',
  add column if not exists market_data_through_utc timestamptz;

alter table public.market_history enable row level security;
alter table public.bot_runtime_status enable row level security;
revoke all on table public.market_history, public.bot_runtime_status from anon, authenticated;
