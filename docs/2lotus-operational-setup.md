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
3. Iniciar todo o runtime persistente com `./scripts/run-2lotus-demo.sh`.
4. Verificar o estado a qualquer momento com `./scripts/check-2lotus-runtime.sh`.

O noVNC fica em `http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080` no próprio servidor.
As portas não devem ser expostas diretamente à internet.

O Docker Compose mantém `2lotus-api` na mesma rede do `2lotus-mt5-desktop`, aplica política
`restart: unless-stopped` e healthchecks aos dois serviços. O perfil de teste força
`DAYTRADE_FIMATH_MODE=shadow` e `DAYTRADE_ENABLE_LIVE_DECISIONS=false`, mesmo que o `.env`
tenha outros valores. A política de fluxo padrão é `veto`: fluxo neutro não elimina o candidato,
mas uma forte contradição simultânea do livro e dos ticks o bloqueia. Para desenvolvimento fora do MT5, `python-service/run-local.sh`
continua disponível.

Após mudanças no código ou nas imagens, reconstruir explicitamente com:

```bash
REBUILD=1 ./scripts/run-2lotus-demo.sh
```

## Configuração no MT5

No desktop remoto, abra **Tools → Options → Expert Advisors**. Marque **Allow WebRequest for listed URL**
e adicione uma única origem:

`http://127.0.0.1:8000`

Depois, compile `SyncLeadBridgeEA.mq5` no MetaEditor e anexe-o a um gráfico `XAUUSD` em `M5`.
Preencha os inputs:

- `StrategyServiceUrl`: `http://127.0.0.1:8000/decision`
- `TradeResultsUrl`: `http://127.0.0.1:8000/api/trades`
- `ResultsBotId`: `bot-1`
- `ShadowBotIds`: `bot-2,bot-3,bot-4` (aceita uma lista separada por vírgulas)
- `HistoryCacheBars`: `2000` por bot, suficiente para aquecimento e histórico recente sem atrasar a inicialização
- `LotusIngestApiKey`: valor de `DAYTRADE_INGEST_API_KEY`
- `EnableOrderExecution`: `false`

Depois de atualizar o EA, recompile-o e remova/anexe novamente ao gráfico. A versão atual converte
os horários do servidor da corretora para UTC antes de persistir candles e negócios; dados antigos
com deslocamento de horário não são reescritos automaticamente.

O MT5 e a API local usam a mesma rede privada de containers; por isso o EA usa `127.0.0.1` sem
expor a API para a rede externa.

## Verificações antes do primeiro trade

```bash
docker exec 2lotus-mt5-desktop curl http://127.0.0.1:8000/health
```

O resultado deve indicar `"status":"ok"`. Após o fechamento de um trade demo, o EA envia um
`POST /api/trades` com a chave no header `X-2Lotus-Ingest-Key`; o painel 2Lotus passa a mostrar a
operação gravada no Supabase.

Durante shadow, confirme também nos logs que os quatro `bot_id` recebem HTTP 200. `strategy_signals`
recebe os candidatos quando cada setup ocorre e `paper_trades` mantém o variant `technical`;
o Bot 1 também acompanha `flow_confirmed`. As chaves de sinal e as consultas de posição são
segmentadas por bot. A execução real só pode ser avaliada depois da
amostra mínima e deve continuar com `EnableOrderExecution=false` até aprovação explícita.

## Segurança e recuperação

- Nunca colocar o valor de `.env` em documentação, GitHub ou mensagens.
- A `service_role` do Supabase fica somente na API; o EA recebe apenas a chave de ingestão.
- Para parar o desktop MT5, use `docker stop 2lotus-mt5-desktop`.
- Para parar a API privada, use `docker stop 2lotus-api`.
- Para parar todo o harness, use `docker compose down`. Os dados persistidos em `.runtime`
  não são removidos.
- Para atualizar a Vercel, publique a partir de `/home/codexops/2Lotus/python-service`.
