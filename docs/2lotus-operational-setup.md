# 2Lotus — ativação operacional

## Identidade e destinos

- Repositório GitHub: `syncleadteam/2Lotus`
- Projeto Vercel: `2lotus`
- Diretório local: `/home/codexops/2Lotus`
- Supabase: `yluszrsumrqzmdueiyyc`

Os identificadores `DAYTRADE_*` no `.env` permanecem por compatibilidade técnica. Eles não são
nomes públicos do produto e não devem ser alterados sem migrar as variáveis da Vercel e o código.

## Antes de iniciar

1. Preencher `/home/codexops/2Lotus/.env` com as credenciais reais.
2. Manter `DAYTRADE_ENABLE_LIVE_DECISIONS=false` durante o teste inicial.
3. Construir o runtime uma vez com `./scripts/build-mt5-runtime.sh`.
4. Iniciar o desktop MT5 com `./scripts/run-mt5-desktop.sh`.
5. Em outro terminal, iniciar a API privada do MT5 com `./scripts/run-mt5-api-sidecar.sh`.

O noVNC fica em `http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080` no próprio servidor.
As portas não devem ser expostas diretamente à internet.

O script da API cria o container `2lotus-api` na mesma rede do `2lotus-mt5-desktop`. Para
desenvolvimento fora do MT5, `python-service/run-local.sh` continua disponível.

## Configuração no MT5

No desktop remoto, abra **Tools → Options → Expert Advisors**. Marque **Allow WebRequest for listed URL**
e adicione uma única origem:

`http://127.0.0.1:8000`

Depois, compile `SyncLeadBridgeEA.mq5` no MetaEditor e anexe-o a um gráfico `XAUUSD` em `M5`.
Preencha os inputs:

- `StrategyServiceUrl`: `http://127.0.0.1:8000/decision`
- `TradeResultsUrl`: `http://127.0.0.1:8000/api/trades`
- `ResultsBotId`: `bot-1`
- `LotusIngestApiKey`: valor de `DAYTRADE_INGEST_API_KEY`
- `EnableOrderExecution`: `false`

O MT5 e a API local usam a mesma rede privada de containers; por isso o EA usa `127.0.0.1` sem
expor a API para a rede externa.

## Verificações antes do primeiro trade

```bash
docker exec 2lotus-mt5-desktop curl http://127.0.0.1:8000/health
```

O resultado deve indicar `"status":"ok"`. Após o fechamento de um trade demo, o EA envia um
`POST /api/trades` com a chave no header `X-2Lotus-Ingest-Key`; o painel 2Lotus passa a mostrar a
operação gravada no Supabase.

## Segurança e recuperação

- Nunca colocar o valor de `.env` em documentação, GitHub ou mensagens.
- A `service_role` do Supabase fica somente na API; o EA recebe apenas a chave de ingestão.
- Para parar o desktop MT5, use `docker stop 2lotus-mt5-desktop`.
- Para parar a API privada, use `docker stop 2lotus-api`.
- Para atualizar a Vercel, publique a partir de `/home/codexops/2Lotus/python-service`.
