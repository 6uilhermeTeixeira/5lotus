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
    -> envia o contexto XAUUSD para bot-6, bot-7, bot-11, bot-12, bot-13 e bot-14
    -> envia contexto EURUSD separado para bot-eur-13
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

- O catálogo separa estratégias `active=true` e `active=false` nas abas `Estratégias ativas` e `Arquivadas`. Os títulos públicos não exibem o identificador técnico `Bot N`.
- O catálogo operacional contém `stochastic_sell_session` (Bot 6), `multitimeframe_trend_pullback` (Bot 7), `portfolio_6_7_100_75` (Bot 11), `happy_gold_zigzag_scalper` (Bot 12), `happy_gold_zigzag_regime_confirmed` (Bot 13) e `happy_gold_zigzag_microstructure` (Bot 14), todos em XAUUSD/M5 e bloqueados em shadow.
- `bot-eur-13` e `bot-btc-13` transferem `happy_gold_zigzag_regime_confirmed` sem recalibração para EURUSD/M5 e BTCUSD/M5. São benchmarks de robustez, não estratégias aprovadas para execução.
- Um único EA consulta apenas esses seis bots a cada ciclo. Estratégias anteriores permanecem consultáveis no painel e no banco para preservar histórico, mas não recebem polling, decisões ou novas operações.
- O Bot 6 replica o setup do Bot 5, mas admite somente vendas antes das 18h UTC; ele permanece isolado em shadow para forward test.
- O Bot 7 deriva candles H1 e M15 completos do histórico canônico M5, exige alinhamento comprador e força mínima de 0,7 ATR(H1), opera somente entre 13h e 16h UTC com metade do risco padrão e permanece bloqueado em shadow.
- O Bot 11 preserva a prioridade 7/6 e a posição única, usando pesos 100/75. O filtro H1 vendedor do Bot 6 é aplicado no motor online, enquanto operações iniciadas, resultado diário e cooldown são lidos dos paper trades persistidos.
- O Bot 12 agrega somente candles M30 completos, identifica pivôs fractais já confirmados como proxy causal do ZigZag e sinaliza seu rompimento no contexto M5. Reproduz lote 0,10, stop de 240 pontos, alvo de 1.000 pontos, posição única e sessão proxy 03:00–19:00 UTC. O break-even entra em +40 pontos, o trailing em +120 com distância de 60 e a posição expira após dois M5; continua travado em shadow porque saídas em segundos ainda dependem de ticks do broker original.
- O Bot 13 mantém a geometria do Bot 12. Range e tendência usam o rompimento-base; transição e alta volatilidade exigem fechamento M5 além do pivô e direção H1 alinhada. O regime é calculado com H1 completo, enquanto o sinal conserva a janela curta do replay-base.
- O Bot 14 mantém o nível M30, mas no forward exige um candle M1 direcional e desequilíbrio de ticks a favor. O EA envia os 20 candles M1 completos e o fluxo acumulado desde o último polling. A gestão dos paper trades usa bid/ask atuais para soft stop, break-even, trailing e timeout em segundos; a série histórica M5 usa uma proxy declarada e não reproduz reentradas intrabar.
- Os setups base continuam consultados no intervalo padrão de cinco segundos. O Bot 14 possui polling separado de um segundo para observar a microestrutura e atualizar sua gestão shadow; nenhuma ordem real é liberada.
- Fluxo amostrado continuamente em janela temporal, com z-scores do livro e dos ticks.
- Política padrão `veto`: somente forte contradição simultânea bloqueia um setup.
- Cada candidato é deduplicado por bot, timeframe, candle, lado e setup; chaves e consultas incluem `bot_id` para impedir colisão entre estratégias.
- Supabase mantém telemetria em `strategy_signals` e paper tracks `technical` e `flow_confirmed`.
- O replay histórico lê `market_candles`, reaplica o motor sem look-ahead e produz resultados efêmeros para o portal, isolados das tabelas operacionais.
- O histórico profundo é canônico por símbolo/timeframe (`bot-1` para XAUUSD/M5, `bot-eur-1` para EURUSD/M5 e `bot-btc-13` para BTCUSD/M5); estratégias não duplicam a mesma série para fins de replay.
- BTCUSD usa o produto spot público BTC-USD da Coinbase Exchange. A origem é exibida nas premissas do replay, pois o servidor MetaQuotes Demo não disponibiliza Bitcoin.
- EURUSD/M5 usa `bot-eur-1` como fonte canônica. `backtest_snapshots` guarda somente o replay compacto, sem duplicar candles, e alimenta o gráfico agregado da tela inicial.
- Um classificador de regime H1 usa ADX, EMA50/EMA200 e percentil de ATR antes de autorizar candidatos no replay.
- Controles de sessão, limite diário, cooldown, spread, slippage e comissão pertencem ao harness e não alteram a geração original dos sinais.
- O cache OHLCV profundo pertence ao mercado e é persistido apenas como `bot-1`; os demais bots reutilizam essa série canônica no replay.
- O gráfico entrega no máximo os 30 dias mais recentes de candles, enquanto métricas e janelas de validação usam todo o período solicitado.
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
