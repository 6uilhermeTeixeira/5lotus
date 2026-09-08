update public.bots
set
  name = 'ZigZag Scalper V2 · Tick Estrutural',
  description = 'Rompimento ZigZag M30 com estrutura M5 e impulso de ticks, sem o filtro de range que reduzia excessivamente a frequência.',
  strategy_profile = 'zigzag_scalper_v2_shadow',
  strategy_description = E'- Status: pesquisa shadow; execução permanentemente bloqueada.\n- Mantém os pivôs causais M30 da ZigZag Scalper original.\n- Exige impulso direcional de 900 segundos >= 1.000 pips e distância direcional da EMA20 >= 900 pips.\n- Aceita extensão máxima de 50 pips além do pivô e exclui sextas-feiras.\n- Remove exclusivamente no V2 o filtro de range normalizado, recuperando sinais sem alterar o V1 ou os experimentos anteriores.\n- Usa stop de 60 pips, breakeven em 40/+1, trailing 40/20 e tempo máximo de 60 segundos.\n- Normaliza o risco monetário ao V1 com lote 0,40 no modelo de pesquisa.\n- Amostra tick estrutural combinada: 164 operações, PF 2,147 e lucro de US$ 609,92 em lote 0,10 antes da normalização.\n- Promoção exige forward test independente com ticks da corretora.'
where id = 'core-zigzag-v2';
