alter table public.bots
  add column if not exists active boolean not null default true;

update public.bots
set active = id in ('bot-6', 'bot-7', 'bot-11', 'bot-12');

create index if not exists bots_active_id_idx
  on public.bots (active, id);

comment on column public.bots.active is
  'Controls operational catalog visibility without deleting historical candles, signals, paper trades, results, or snapshots.';

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
