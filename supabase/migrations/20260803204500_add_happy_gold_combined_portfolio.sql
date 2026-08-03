update public.bots
set name = 'Portfólio 7/6 · 100/100',
    description = 'Portfólio shadow com Bot 7 e Bot 6 usando 100% do risco-base, posição e limites diários compartilhados.',
    strategy_profile = 'portfolio_6_7_100_100',
    strategy_description = E'- Status: promising_not_live, permanentemente bloqueada em shadow.\n- Mercado: somente XAUUSD/M5.\n- Bot 7: 100% do risco-base, mantendo tendência H1/M15, pullback M5 e prioridade sobre conflitos.\n- Bot 6: 100% do risco-base, somente vendas antes de 18 UTC e com tendência H1 de baixa confirmada.\n- Os pesos nunca representam posições simultâneas: uma única exposição é compartilhada.\n- Risco persistido: no máximo duas entradas por dia, limite diário de 2R e cooldown de 15 minutos após perda.\n- Replay anual: 171 trades, US$ 1.112,20, PF 1,80, expectativa +0,2477R, drawdown 6,10R e 12/12 janelas positivas.\n- Validação: passou o gate inicial, mas permanece somente para comparação e forward test em shadow.'
where id = 'bot-11';

insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-16',
  'Happy Gold + Portfólio 7/6 · 100/100',
  'Meta-portfólio shadow que coordena a confirmação de regime do ZigZag com os componentes 7/6 em risco 100/100.',
  'happy_gold_portfolio_100_100',
  E'- Status: promising_not_live, permanentemente bloqueada em shadow.\n- Componentes: Happy Gold ZigZag · Confirmação de Regime e Portfólio 7/6 · 100/100.\n- Independência: cada setup conserva suas regras de entrada e saída; a camada superior apenas seleciona e controla o risco.\n- Prioridade: ZigZag confirmado primeiro; depois Bot 7 e Bot 6. Sinais simultâneos em direções opostas são bloqueados.\n- Risco: qualquer componente usa no máximo 100% do risco-base, sem somar lotes; existe somente uma posição XAUUSD.\n- Limites compartilhados: duas entradas por dia, perda máxima diária de 2R e cooldown de 15 minutos após perda.\n- Replay anual: 427 trades, US$ 2.118,89, PF 1,38, expectativa +0,1822R, drawdown 14,75R e 11/13 janelas positivas.\n- Validação: passou o gate inicial, mas o drawdown é materialmente maior que no 7/6 isolado; requer forward test em shadow.',
  'XAUUSD',
  'M5',
  true
)
on conflict (id) do update
set name = excluded.name,
    description = excluded.description,
    strategy_profile = excluded.strategy_profile,
    strategy_description = excluded.strategy_description,
    symbol = excluded.symbol,
    timeframe = excluded.timeframe,
    active = excluded.active;

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
