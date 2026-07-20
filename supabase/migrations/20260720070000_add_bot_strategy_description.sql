alter table public.bots
  add column if not exists strategy_description text not null default '';

update public.bots
set strategy_description = description
where strategy_description = '';

comment on column public.bots.strategy_description is
  'Texto livre exibido no card de estratégia da página de resultados.';
