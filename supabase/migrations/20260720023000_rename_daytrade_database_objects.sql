create or replace function public.set_2lotus_updated_at()
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
for each row execute function public.set_2lotus_updated_at();

drop trigger if exists set_trade_results_updated_at on public.trade_results;
create trigger set_trade_results_updated_at
before update on public.trade_results
for each row execute function public.set_2lotus_updated_at();

drop function if exists public.set_daytrade_updated_at();
