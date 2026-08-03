insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe, active
)
values (
  'bot-14',
  'Happy Gold ZigZag · Microestrutura',
  'Variante shadow que confirma o rompimento com M1 e fluxo de ticks e encerra sinais sem continuidade rapidamente.',
  'happy_gold_zigzag_microstructure',
  E'- Status: candidato experimental permanentemente bloqueado em shadow.\n- Estrutura: mantém o pivô fractal M30 causal, lote fixo de 0,10, SL emergencial de 240 pontos e TP de 1.000 pontos.\n- Entrada forward: exige candle M1 direcional, pelo menos 4 ticks direcionais na janela, desequilíbrio mínimo de 25%, livro sem oposição forte e extensão máxima de 80 pontos além do pivô.\n- Gestão forward com bid/ask amostrado a cada segundo: saída defensiva em 40 pontos adversos, break-even em +30 com trava de +5, trailing em +60 com distância de 30 e encerramento após 60 segundos.\n- Reentrada: uma nova observação pode ser registrada a cada janela de 15 segundos quando não existe posição aberta.\n- Replay: o histórico canônico disponível é M5; corpo, posição do fechamento e volume são usados somente como proxy, sem alegar reprodução de ticks ou múltiplas reentradas intrabar.\n- Resultado da proxy M5 em 365 dias: 108 operações, 16,67% de acerto, PnL US$ 15,10, PF 1,04 e drawdown 5,87R; status rejeitado para seleção histórica.\n- Interpretação: a precedência conservadora do soft stop quando um M5 toca os dois lados reduz artificialmente o win rate; somente o forward com fluxo de ticks pode testar a hipótese original.\n- Validação: a promoção depende do forward test com o EA atualizado e de estabilidade fora da amostra; win rate isolado não autoriza execução real.',
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
