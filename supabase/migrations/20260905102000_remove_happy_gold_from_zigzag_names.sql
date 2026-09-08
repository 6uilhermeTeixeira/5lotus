update public.bots
set
  name = replace(
    replace(
      replace(name, 'Happy Gold · ZigZag', 'ZigZag Scalper'),
      'Happy Gold ZigZag',
      'ZigZag Scalper'
    ),
    'Happy Gold',
    'ZigZag Scalper'
  ),
  description = replace(
    replace(
      replace(description, 'Happy Gold · ZigZag', 'ZigZag Scalper'),
      'Happy Gold ZigZag',
      'ZigZag Scalper'
    ),
    'Happy Gold',
    'ZigZag Scalper'
  ),
  strategy_description = replace(
    replace(
      replace(strategy_description, 'Happy Gold · ZigZag', 'ZigZag Scalper'),
      'Happy Gold ZigZag',
      'ZigZag Scalper'
    ),
    'Happy Gold',
    'ZigZag Scalper'
  )
where strategy_profile like 'happy_gold%';
