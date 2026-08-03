update public.bots
set description = 'Meta-portfólio shadow com risco-base de replay em 2%, sessão recalibrada e quantidade de entradas sem limite fixo.',
    strategy_description = E'- Status: promising_not_live, permanentemente bloqueada em shadow.\n- Componentes: Happy Gold ZigZag · Confirmação de Regime e Portfólio 7/6 · 100/100.\n- Sessão recalibrada: 06:00–19:00 UTC, escolhida entre seis janelas pela relação entre PF, estabilidade e drawdown.\n- Risco do replay: 2% da banca por operação, com compounding.\n- Operações: sem limite fixo de quantidade; posição única, cooldown de 15 minutos e perda máxima diária de 2R permanecem ativos.\n- Conflitos: sinais em direções opostas são bloqueados; o ZigZag confirmado tem prioridade quando existe concordância.\n- Replay anual: 795 trades, PF 1,21, expectativa +0,1656R, drawdown 13,84R e 9/13 janelas positivas.\n- PnL composto: US$ 98.002,76 sobre banca inicial de US$ 10.000; altamente sensível ao risco de 2% e não representa projeção.\n- Validação: passou o gate inicial, mas exige forward test em shadow devido ao risco e ao efeito do compounding.'
where id = 'bot-16';

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
