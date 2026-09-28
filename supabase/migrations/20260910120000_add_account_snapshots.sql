create table if not exists public.account_snapshots (
  snapshot_key text primary key default 'current',
  account_id bigint unique check (account_id > 0),
  broker text not null default '',
  server text not null default '',
  currency text not null default 'USD',
  trade_mode text not null default 'unknown' check (trade_mode in ('demo', 'contest', 'real', 'unknown')),
  leverage integer,
  balance numeric not null,
  equity numeric not null,
  margin_free numeric not null,
  floating_profit numeric not null default 0,
  realized_profit_today numeric,
  profit_day date,
  observed_at_utc timestamptz not null,
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists account_snapshots_observed_at_idx
  on public.account_snapshots (observed_at_utc desc);

drop trigger if exists set_account_snapshots_updated_at on public.account_snapshots;
create trigger set_account_snapshots_updated_at
before update on public.account_snapshots
for each row execute function public.set_2lotus_updated_at();

alter table public.account_snapshots enable row level security;
revoke all on table public.account_snapshots from anon, authenticated;
