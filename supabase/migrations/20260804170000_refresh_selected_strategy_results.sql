update public.bots
set description = 'Meta-portfólio shadow com risco-base de 0,25%, sessão 06:00–19:00 UTC e posição única compartilhada.',
    strategy_description = E'- Status: promising_not_live, permanentemente bloqueada em shadow.\n- Componentes: Happy Gold ZigZag · Confirmação de Regime e Portfólio 7/6 · 100/100.\n- Sessão: 06:00–19:00 UTC.\n- Risco do replay: 0,25% da banca por operação, com composição.\n- Operações: posição única, cooldown após perda e perda máxima diária de 2R; sem limite fixo de entradas.\n- Conflitos: sinais opostos são bloqueados e o ZigZag confirmado tem prioridade quando existe concordância.\n- Replay anual atualizado em 2026-08-04: 797 operações, PnL de US$ 3.933,44, PF 1,35 e validação promising_not_live.\n- Uso: pesquisa e forward test em shadow; não representa projeção nem autoriza execução real.'
where id = 'bot-16';

update public.bots
set strategy_description = regexp_replace(strategy_description, 'Replay integrado de 365 dias:[^\n]*', 'Replay anual atualizado em 2026-08-04: 606 operações, PnL de US$ 2.657,30 e PF 1,40.')
where id = 'bot-13';

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
