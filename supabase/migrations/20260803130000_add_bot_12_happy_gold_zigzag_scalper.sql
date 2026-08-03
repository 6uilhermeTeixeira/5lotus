insert into public.bots (
  id, name, description, strategy_profile, strategy_description, symbol, timeframe
)
values (
  'bot-12',
  'Bot 12 — Happy Gold ZigZag Scalper',
  'Réplica experimental da assinatura observada em 773 operações XAUUSD, permanentemente bloqueada em shadow.',
  'happy_gold_zigzag_scalper',
  E'- Status: engenharia reversa experimental, permanentemente bloqueada em shadow.\n- Mercado: somente XAUUSD/M5; o sinal agrega candles M30 completos.\n- Entrada: rompimento de pivô fractal M30 confirmado, aproximação causal e sem repaint do ZigZag proprietário.\n- Exposição: uma posição por vez e lote fixo de 0,10, como na amostra de 773 operações.\n- Geometria: stop emergencial de 240 pontos e alvo de 1.000 pontos.\n- Gestão: break-even em +40 pontos no preço de entrada, trailing após +120 pontos com distância de 60 e saída máxima após dois candles M5.\n- Sessão: proxy 03:00–19:00 UTC, pendente de confirmação do fuso do broker original.\n- Replay de seleção: 821 operações em 365 dias, PF 1,33, expectativa 0,153R e drawdown máximo 25,15R sob as premissas OHLC configuradas.\n- Limitação: não é cópia do código proprietário; é uma reconstrução testável da assinatura estatística observada.',
  'XAUUSD',
  'M5'
)
on conflict (id) do update
set name = excluded.name,
    description = excluded.description,
    strategy_profile = excluded.strategy_profile,
    strategy_description = excluded.strategy_description,
    symbol = excluded.symbol,
    timeframe = excluded.timeframe;

alter table public.bots enable row level security;
revoke all on table public.bots from anon, authenticated;
