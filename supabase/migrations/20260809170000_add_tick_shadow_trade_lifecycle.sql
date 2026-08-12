create table if not exists public.tick_shadow_trades (
  signal_key text primary key references public.strategy_signals(signal_key) on delete cascade,
  bot_id text not null references public.bots(id) on delete cascade,
  symbol text not null,
  side text not null check (side in ('buy', 'sell')),
  status text not null default 'open' check (status in ('open', 'closed')),
  opened_at_utc timestamptz not null,
  opened_time_msc bigint not null check (opened_time_msc > 0),
  closed_at_utc timestamptz,
  closed_time_msc bigint,
  entry_price double precision not null,
  volume_lots double precision not null default 0.10 check (volume_lots > 0),
  initial_stop_price double precision not null,
  stop_price double precision not null,
  target_price double precision,
  best_price double precision not null,
  exit_price double precision,
  exit_reason text check (exit_reason is null or exit_reason in ('stop', 'target', 'time')),
  pip_size double precision not null check (pip_size > 0),
  value_per_pip double precision not null check (value_per_pip > 0),
  break_even_trigger_pips double precision not null,
  break_even_offset_pips double precision not null,
  trailing_activation_pips double precision not null,
  trailing_distance_pips double precision not null,
  max_holding_seconds integer not null check (max_holding_seconds > 0),
  pnl_pips double precision,
  net_pnl double precision,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  check (
    (status = 'open' and closed_at_utc is null and exit_price is null)
    or (status = 'closed' and closed_at_utc is not null and exit_price is not null)
  )
);

create index if not exists tick_shadow_trades_open_symbol_idx
  on public.tick_shadow_trades (symbol, status, opened_time_msc)
  where status = 'open';

create unique index if not exists tick_shadow_trades_one_open_per_bot_idx
  on public.tick_shadow_trades (bot_id)
  where status = 'open';

alter table public.tick_shadow_trades enable row level security;
revoke all on table public.tick_shadow_trades from anon, authenticated;

comment on table public.tick_shadow_trades is
  'Tick-executable shadow lifecycle. Research only; rows never create or modify broker orders.';
