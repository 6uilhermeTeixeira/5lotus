-- Keep only the three adaptive V3 strategies and their parallel combination in
-- the active Live Core catalog. Execution remains protected by the existing
-- strategy-level shadow locks until a separate, explicit live promotion.
update public.bots
set active = id in (
  'core-zigzag-v3',
  'core-stochastic-v3',
  'core-multitimeframe-v3',
  'core-combined-v3'
)
where id like 'core-%';

update public.bots
set name = 'Portfólio Combinado V3'
where id = 'core-combined-v3';
