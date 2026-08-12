alter table public.bot_runtime_status
  add column if not exists last_attempt_at_utc timestamptz,
  add column if not exists last_success_at_utc timestamptz,
  add column if not exists last_error_code text;

create table if not exists public.decision_requests (
  bot_id text not null references public.bots(id) on delete cascade,
  request_id text not null,
  response jsonb not null,
  created_at timestamptz not null default timezone('utc', now()),
  primary key (bot_id, request_id)
);

create index if not exists decision_requests_created_at_idx
  on public.decision_requests (created_at desc);

alter table public.decision_requests enable row level security;
revoke all on table public.decision_requests from anon, authenticated;
