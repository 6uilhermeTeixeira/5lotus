delete from public.bots
where id in (
  'bot-1', 'bot-2', 'bot-3', 'bot-4', 'bot-5', 'bot-8', 'bot-9', 'bot-10', 'bot-15',
  'bot-eur-1', 'bot-eur-2', 'bot-eur-3', 'bot-eur-4', 'bot-eur-5', 'bot-eur-6', 'bot-eur-7'
);

drop table if exists public.market_candles;

update public.bots
set description = 'Meta-portfólio shadow com risco-base de replay em 0,25%, sessão 06:00–19:00 UTC e posição única compartilhada.',
    strategy_description = E'- Status: promising_not_live, permanentemente bloqueada em shadow.\n- Componentes: Happy Gold ZigZag · Confirmação de Regime e Portfólio 7/6 · 100/100.\n- Sessão: 06:00–19:00 UTC.\n- Risco do replay: 0,25% da banca por operação, com composição.\n- Operações: posição única, cooldown após perda e perda máxima diária de 2R; sem limite fixo de entradas.\n- Conflitos: sinais opostos são bloqueados e o ZigZag confirmado tem prioridade quando existe concordância.\n- Replay anual recalculado: 802 operações, PnL de US$ 3.891,74, PF 1,35 e validação promising_not_live.\n- Uso: pesquisa e forward test em shadow; não representa projeção nem autoriza execução real.'
where id = 'bot-16';

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
