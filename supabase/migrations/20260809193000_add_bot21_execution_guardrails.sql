update public.bots
set strategy_description = strategy_description
    || E'\n- Robustez operacional: 16/16 cenários lucrativos entre spread 5-20 e latência 0-1.000 ms.\n- Guardrail shadow: spread máximo 15 pontos/pips e meta de latência até 500 ms; acima disso a margem degradou.'
where id = 'bot-21';
