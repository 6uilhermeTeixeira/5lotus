# Playbook de Teste em Demo

## Objetivo

Executar um teste fim a fim do fluxo:

`MT5 -> EA MQL5 -> Python strategy service -> decisao -> envio de ordem`

no ambiente demo do projeto.

## Estado atual

Em **sábado, 18 de julho de 2026**, o mercado do `XAUUSD` normalmente estara fechado.

Isso significa:

- o teste de conectividade pode ser executado agora
- o teste de decisao pode ser executado agora
- o teste de envio real de ordem depende da reabertura do mercado e de ticks no terminal

## Dependencias operacionais

Hoje existem dois detalhes importantes:

1. o MT5 roda dentro de um container Docker, entao `127.0.0.1` dentro do terminal nao enxerga o servico Python do host
2. o EA precisa ser copiado/compilado dentro do ambiente MT5 manualmente

## Preparacao

### 1. Subir o servico Python

Para teste seguro, sem liberar execucao automatica:

```bash
cd /home/codexops/workspace/daytrade/python-service
DAYTRADE_ENABLE_LIVE_DECISIONS=false .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir .
```

Para permitir que o servico retorne `buy` ou `sell` quando o setup estiver valido:

```bash
cd /home/codexops/workspace/daytrade/python-service
DAYTRADE_ENABLE_LIVE_DECISIONS=true .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir .
```

### 2. Subir o desktop remoto do MT5

```bash
cd /home/codexops/workspace/daytrade
./scripts/run-mt5-desktop.sh
```

### 3. Abrir a sessao grafica

No navegador, abrir:

```text
http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080
```

## Descobrir o IP do host para o container

O EA dentro do MT5 precisa chamar o servico Python usando o IP do host visto pelo container.

Descobrir com:

```bash
docker exec daytrade-mt5-desktop sh -lc "ip route | awk '/default/ {print \$3}'"
```

Exemplo de retorno esperado:

```text
172.17.0.1
```

## Validar conectividade do container para o servico

Antes de abrir o MT5, validar com:

```bash
docker exec daytrade-mt5-desktop curl http://172.17.0.1:8000/health
```

Resposta esperada:

```json
{"status":"ok","service":"mt5-daytrade-strategy-service", ...}
```

Se isso falhar, o problema ainda e de rede, nao de estrategia.

## Copiar o EA para o ambiente do MT5

```bash
docker cp /home/codexops/workspace/daytrade/mt5/experts/SyncLeadBridgeEA.mq5 daytrade-mt5-desktop:/data/home/SyncLeadBridgeEA.mq5
```

## Configurar o MT5

Dentro do desktop remoto:

1. abrir o `MetaEditor`
2. abrir `Z:\data\home\SyncLeadBridgeEA.mq5`
3. compilar o EA
4. no MT5, abrir `Tools > Options > Expert Advisors`
5. marcar `Allow algorithmic trading`
6. adicionar `http://172.17.0.1:8000` na allowlist de `WebRequest`
7. abrir um grafico `XAUUSD`
8. ajustar o grafico para `M5`
9. anexar o EA ao grafico

## Inputs recomendados do EA

### Fase 1: conectividade e decisao sem ordem

- `StrategyServiceUrl = http://172.17.0.1:8000/decision`
- `StrategyTimeframe = M5`
- `HistoryBars = 30`
- `EnableOrderExecution = false`

### Fase 2: ordem automatica em demo

- `StrategyServiceUrl = http://172.17.0.1:8000/decision`
- `StrategyTimeframe = M5`
- `HistoryBars = 30`
- `EnableOrderExecution = true`

Essa segunda fase so faz sentido quando:

- o servico Python estiver com `DAYTRADE_ENABLE_LIVE_DECISIONS=true`
- houver ticks reais no `XAUUSD`
- o terminal estiver conectado na conta demo

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
