-- Remove os experimentos rejeitados. As FKs relacionadas usam ON DELETE CASCADE,
-- eliminando também candles, snapshots, sinais e operações vinculados.
delete from public.bots
where id in ('bot-14', 'bot-eur-13', 'bot-btc-13');

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
