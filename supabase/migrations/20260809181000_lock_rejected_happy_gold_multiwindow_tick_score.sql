update public.bots
set description = 'Hipótese multijanela rejeitada no replay exaustivo de ticks; preservada para auditoria.',
    strategy_description = E'- Status: rejeitado no replay exaustivo; execução e geração de candidatos bloqueadas.\n- Evidência inicial: 95 entradas contra 470 controles pareados sugeriram discriminação local.\n- Replay exaustivo: 43.610 sinais, 45,97% de acerto, profit factor 0,806 e PnL de -US$ 34.047,50.\n- Cooldown de 90 minutos: 1.044 sinais e profit factor 0,846.\n- Cooldown de 150 minutos: 674 sinais e profit factor 0,818.\n- Conclusão: aceleração multijanela descreve entradas conhecidas, mas não identifica o mecanismo seletivo do bot original.'
where id = 'bot-20';
