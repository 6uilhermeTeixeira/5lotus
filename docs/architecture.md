# Arquitetura operacional

## Recomendacao

Arquitetura hibrida:

1. `Expert Advisor MQL5` dentro do MT5
2. `Python strategy service` rodando no Linux
3. `HTTP local` como canal entre execucao e estrategia

## Motivo

Essa separacao respeita melhor as restricoes do ambiente:

- MT5 executa no runtime que ele suporta
- Python roda nativamente no Linux desta maquina
- a estrategia pode evoluir sem acoplar a logica ao terminal

## Fluxo

```text
MT5 terminal
  -> Expert Advisor MQL5
    -> coleta estado do mercado / conta / posicoes
    -> envia o mesmo contexto para bot-1, bot-2, bot-3 e bot-4
Python strategy service
  -> seleciona a estratégia pelo perfil cadastrado do bot
  -> aplica risco
  -> responde: buy / sell / close / hold
Expert Advisor MQL5
  -> valida resposta
  -> envia ordem no MT5
  -> registra resultado
```

## Estado atual

- Estratégias `fimath_ema20_flow`, `momentum_atr_breakout`, `rsi_bollinger_reversion` e `macd_trend_crossover` para XAUUSD/M5.
- Um único EA consulta os quatro bots a cada ciclo; apenas o bot primário poderia receber autorização de execução.
- Setup técnico calculado uma vez por candle fechado e resposta consultada pelo EA a cada cinco segundos.
- Fluxo amostrado continuamente em janela temporal, com z-scores do livro e dos ticks.
- Política padrão `veto`: somente forte contradição simultânea bloqueia um setup.
- Cada candidato é deduplicado por bot, timeframe, candle, lado e setup; chaves e consultas incluem `bot_id` para impedir colisão entre estratégias.
- Supabase mantém telemetria em `strategy_signals` e paper tracks `technical` e `flow_confirmed`.
- Candles e negócios originados no horário do servidor MT5 são convertidos para UTC no EA.
- API e EA permanecem em shadow/execução desligada no Compose.

## Componentes

### 1. MT5 / MQL5

Responsabilidades:

- receber ticks e eventos de mercado
- montar contexto minimo da decisao
- executar ordens
- confirmar fills, rejeicoes e posicoes
- fazer retry controlado apenas quando explicitamente permitido

### 2. Python strategy service

Responsabilidades:

- gerar sinal
- validar horario e sessao
- validar limites de risco
- aplicar filtros de spread, volatilidade e exposicao
- expor endpoints locais de saude e decisao

### 3. Persistência Supabase

- `market_candles`: cache OHLCV.
- `strategy_signals`: candidato, payload, resposta, motivo e métricas de fluxo.
- `paper_trades`: resultados comparáveis por variant, sem posições sobrepostas em cada track.
- `trade_results`: negócios realmente encerrados no MT5.

RLS permanece habilitado e os papéis `anon`/`authenticated` não recebem acesso; a escrita
privilegiada fica restrita ao serviço Python.

## Alternativas avaliadas

### Opcao A: tudo em MQL5

Vantagem:

- execucao mais simples dentro do MT5

Desvantagem:

- pior ergonomia para testes, analytics e evolucao do modelo

### Opcao B: Python falando direto com MetaTrader5

Vantagem:

- stack unica em Python

Desvantagem:

- neste host Linux depende de Wine + terminal + setup mais fragil
- maior risco operacional para um primeiro ciclo

## Decisao inicial

Comecar com:

- `MQL5` para execucao
- `Python` para estrategia e risco

Se depois o ambiente Wine ficar robusto e controlado, podemos reavaliar a interface Python direta com o terminal.
