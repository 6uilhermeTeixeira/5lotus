create table if not exists public.bots (
  id text primary key check (id ~ '^[a-z0-9-]+$'),
  name text not null,
  description text not null default '',
  strategy_profile text not null,
  symbol text not null,
  timeframe text not null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.trade_results (
  bot_id text not null references public.bots(id) on delete cascade,
  trade_id text not null,
  symbol text not null,
  timeframe text not null,
  setup text not null,
  side text not null check (side in ('buy', 'sell')),
  opened_at_utc timestamptz not null,
  closed_at_utc timestamptz,
  volume_lots numeric not null,
  entry_price numeric not null,
  exit_price numeric,
  stop_loss_price numeric,
  take_profit_price numeric,
  risk_amount numeric not null default 0,
  gross_pnl numeric not null default 0,
  fees numeric not null default 0,
  net_pnl numeric not null default 0,
  rr_realized numeric,
  note text not null default '',
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  primary key (bot_id, trade_id)
);

create index if not exists trade_results_bot_closed_at_idx
  on public.trade_results (bot_id, closed_at_utc desc nulls last);

create or replace function public.set_daytrade_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists set_bots_updated_at on public.bots;
create trigger set_bots_updated_at
before update on public.bots
for each row execute function public.set_daytrade_updated_at();

drop trigger if exists set_trade_results_updated_at on public.trade_results;
create trigger set_trade_results_updated_at
before update on public.trade_results
for each row execute function public.set_daytrade_updated_at();

alter table public.bots enable row level security;
alter table public.trade_results enable row level security;

revoke all on table public.bots from anon, authenticated;
revoke all on table public.trade_results from anon, authenticated;

insert into public.bots (id, name, description, strategy_profile, symbol, timeframe)
values (
  'bot-1',
  'Bot 1',
  'Teste demonstrativo da estrategia de breakout com pullback.',
  'price_action_breakout_pullback',
  'XAUUSD',
  'M5'
)
on conflict (id) do nothing;
