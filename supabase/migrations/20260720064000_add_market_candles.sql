create table if not exists public.market_candles (
  bot_id text not null references public.bots(id) on delete cascade,
  symbol text not null,
  timeframe text not null,
  timestamp_utc timestamptz not null,
  open numeric not null,
  high numeric not null,
  low numeric not null,
  close numeric not null,
  volume numeric not null default 0,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  primary key (bot_id, symbol, timeframe, timestamp_utc)
);

create index if not exists market_candles_bot_time_idx
  on public.market_candles (bot_id, symbol, timeframe, timestamp_utc desc);

drop trigger if exists set_market_candles_updated_at on public.market_candles;
create trigger set_market_candles_updated_at
before update on public.market_candles
for each row execute function public.set_2lotus_updated_at();

alter table public.market_candles enable row level security;
revoke all on table public.market_candles from anon, authenticated;
