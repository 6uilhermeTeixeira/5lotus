# Playbook de Teste em Demo

## Objetivo

Executar um teste fim a fim do fluxo:

`MT5 -> EA MQL5 -> Python strategy service -> decisao -> envio de ordem`

no ambiente demo do projeto.

## Estado atual

O teste de ordem deve ser feito quando o `XAUUSD` estiver aberto e recebendo ticks.

Isso significa:

- o teste de conectividade pode ser executado agora
- o teste de decisao pode ser executado agora
- o teste de envio real de ordem depende da reabertura do mercado e de ticks no terminal

## Dependencias operacionais

O MT5 e o servico Python compartilham a rede no Compose; por isso o EA usa
`127.0.0.1:7775`. O EA ainda precisa ser instalado e compilado no MetaEditor.

## Preparacao

### 1. Subir o servico Python

Para teste seguro, sem liberar execucao automatica:

```bash
cd /home/codexops/projects/5lotus
docker compose up -d api
```

Para permitir que o servico retorne `buy` ou `sell` quando o setup estiver valido:

```bash
Defina `DAYTRADE_ENABLE_LIVE_DECISIONS=true` no `.env` apenas durante a fase
controlada em demo e recrie o servico `api`.
```

### 2. Subir o desktop remoto do MT5

```bash
cd /home/codexops/projects/5lotus
./scripts/run-mt5-desktop.sh
```

### 3. Abrir a sessao grafica

No navegador, abrir:

```text
http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080
```

## Validar conectividade do container para o servico

Antes de abrir o MT5, validar com:

```bash
docker exec 2lotus-mt5-desktop curl http://127.0.0.1:7775/health
```

Resposta esperada:

```json
{"status":"ok","service":"5lotus-research", ...}
```

Se isso falhar, o problema ainda e de rede, nao de estrategia.

## Copiar o EA para o ambiente do MT5

```bash
cd /home/codexops/projects/5lotus
./scripts/install-mt5-expert.sh
```

## Configurar o MT5

Dentro do desktop remoto:

1. abrir o `MetaEditor`
2. abrir `Z:\data\home\SyncLeadBridgeEA.mq5`
3. compilar o EA
4. no MT5, abrir `Tools > Options > Expert Advisors`
5. marcar `Allow algorithmic trading`
6. adicionar `http://127.0.0.1:7775` na allowlist de `WebRequest`
7. abrir um grafico `XAUUSD`
8. ajustar o grafico para `M5`
9. anexar o EA ao grafico

## Inputs recomendados do EA

### Fase 1: conectividade e decisao sem ordem

- `StrategyServiceUrl = http://127.0.0.1:7775/decision`
- `TradeResultsUrl = http://127.0.0.1:7775/api/trades`
- `ResultsBotId = core-combined-v3`
- `LotusIngestApiKey =` valor de `DAYTRADE_INGEST_API_KEY` do `.env` do 2Lotus
- `StrategyTimeframe = M5`
- `HistoryBars = 4000`
- `EnableOrderExecution = false`
- `ExecutionBotId =` vazio

### Fase 2: ordem automatica em demo

- `StrategyServiceUrl = http://127.0.0.1:7775/decision`
- `TradeResultsUrl = http://127.0.0.1:7775/api/trades`
- `ResultsBotId =` o mesmo bot individual definido em `ExecutionBotId`
- `StrategyTimeframe = M5`
- `HistoryBars = 4000`
- `EnableOrderExecution = true`
- `ExecutionBotId = core-zigzag-v3`, `core-stochastic-v3` ou `core-multitimeframe-v3`

Essa segunda fase so faz sentido quando:

- o servico Python estiver com `DAYTRADE_ENABLE_LIVE_DECISIONS=true`
- houver ticks reais no `XAUUSD`
- o terminal estiver conectado na conta demo
- somente uma estrategia individual estiver selecionada para execucao

`core-combined-v3` ainda nao pode executar ordens: sua resposta contem varios
`parallel_candidates`, enquanto o EA atual executa apenas uma decisao simples.

## Fases do teste

### Fase A: teste de conectividade

Objetivo:

- provar que o EA consegue falar com o servico Python

Esperado:

- log do EA com resposta JSON do endpoint `/decision`
- nenhuma tentativa de ordem

### Fase B: teste de decisao com trava ativa

Condicoes:

- `DAYTRADE_ENABLE_LIVE_DECISIONS=false`
- `EnableOrderExecution=false`

Objetivo:

- validar a deteccao do setup automatico sem enviar ordem

Resultados esperados:

- `setup_not_confirmed` quando o mercado nao atender as regras
- `live_decisions_disabled` quando o setup atender as regras
- resposta com:
  - `suggested_action`
  - `suggested_size`
  - `entry_price`
  - `stop_loss_price`
  - `take_profit_price`

### Fase C: decisao liberada, ordem ainda travada

Condicoes:

- `DAYTRADE_ENABLE_LIVE_DECISIONS=true`
- `EnableOrderExecution=false`

Objetivo:

- validar que o servico passa a retornar `buy` ou `sell` em vez de `hold`

Esperado:

- o EA recebe a resposta executavel
- nenhuma ordem ainda e enviada

### Fase D: ordem real em demo

Condicoes:

- `DAYTRADE_ENABLE_LIVE_DECISIONS=true`
- `EnableOrderExecution=true`

Objetivo:

- validar o fluxo completo com ordem no terminal

Esperado:

- abertura de ordem em demo
- posicionamento de `SL` e `TP`
- logs coerentes no EA e no servico

## Onde observar

### No servico Python

Console do `uvicorn`:

- requests recebidas
- `action`
- `reason`

### No MT5

- aba `Experts`
- aba `Journal`

### No desktop remoto

- confirmacao de conexao da conta demo
- presenca de ticks no `XAUUSD`
- anexacao correta do EA no grafico `M5`

## Causas comuns de falha

### 1. `WebRequest failed`

Causa comum:

- URL nao incluida na allowlist
- IP do host incorreto
- servico Python escutando so em `127.0.0.1`

### 2. Resposta sempre `insufficient_history`

Causa comum:

- `HistoryBars` insuficiente
- grafico acabou de ser aberto e o terminal ainda nao carregou candles suficientes

### 3. Resposta sempre `market_filter_mismatch`

Causa comum:

- simbolo diferente de `XAUUSD`
- timeframe diferente de `M5`

### 4. Nao envia ordem mesmo com setup confirmado

Causa comum:

- `DAYTRADE_ENABLE_LIVE_DECISIONS=false`
- `EnableOrderExecution=false`

### 5. Nao abre ordem apesar de `buy`/`sell`

Causa comum:

- mercado fechado
- conta demo sem permissao de trade
- volume fora do range permitido do ativo

## Checklist minimo para teste real em demo

- servico Python no ar
- `curl` do container para `/health` retornando `200`
- conta demo conectada no MT5
- grafico `XAUUSD` aberto em `M5`
- EA compilado e anexado
- allowlist de `WebRequest` configurada
- `DAYTRADE_ENABLE_LIVE_DECISIONS=true`
- `EnableOrderExecution=true`

## Melhorias recomendadas

Para reduzir operacao manual no proximo ciclo:

1. expor `host.docker.internal` no runtime do MT5
2. montar `mt5/experts` diretamente no ambiente do terminal
3. adicionar parser JSON mais robusto no EA
4. adicionar bloqueio de duplicidade de ordem por candle
5. registrar `ticket`, `SL`, `TP` e retcodes em log estruturado
