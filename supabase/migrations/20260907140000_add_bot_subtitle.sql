alter table public.bots
  add column if not exists subtitle text not null default '',
  add column if not exists results_file text not null default '';

comment on column public.bots.subtitle is
  'Rótulo curto da variante exibido abaixo do nome da estratégia.';

comment on column public.bots.results_file is
  'Caminho relativo do snapshot JSON usado quando o catálogo roda fora do Supabase.';
