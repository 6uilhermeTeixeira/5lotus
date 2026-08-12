create table if not exists public.market_ticks (
  collector_id text not null,
  symbol text not null,
  time_msc bigint not null check (time_msc > 0),
  sequence bigint not null check (sequence >= 0),
  timestamp_utc timestamptz generated always as (to_timestamp(time_msc::double precision / 1000.0)) stored,
  bid double precision not null check (bid > 0),
  ask double precision not null check (ask >= bid),
  last double precision not null default 0 check (last >= 0),
  volume bigint not null default 0 check (volume >= 0),
  volume_real double precision not null default 0 check (volume_real >= 0),
  flags integer not null default 0 check (flags >= 0),
  point_size double precision not null check (point_size > 0),
  created_at timestamptz not null default timezone('utc', now()),
  primary key (collector_id, symbol, time_msc, sequence)
);

create index if not exists market_ticks_symbol_time_idx
  on public.market_ticks (symbol, time_msc);

alter table public.market_ticks enable row level security;
revoke all on table public.market_ticks from anon, authenticated;

comment on table public.market_ticks is
  'Raw broker ticks for shadow research. Service-role ingestion only; never an execution trigger by itself.';
