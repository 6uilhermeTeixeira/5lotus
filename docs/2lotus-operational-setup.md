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
- `ResultsBotId`: `bot-6`
- `ShadowBotIds`: `bot-2,bot-3,bot-4,bot-5` (aceita uma lista separada por vírgulas)
- `ExperimentalBotId`: `bot-6` (força o polling do experimento mesmo em gráficos que preservam a lista shadow antiga)
- `MultitimeframeResearchBotId`: `bot-7` (força o polling do experimento multitemporal sempre sem execução)
- `PortfolioResearchBotId`, `AdaptivePortfolioResearchBotId` e `BalancedPortfolioResearchBotId`: legados, ignorados pelo polling
- `AggressivePortfolioResearchBotId`: `bot-11` (força o polling da variante 100/100 sempre sem execução)
- `HappyGoldResearchBotId`: `bot-12` (força o polling da reconstrução ZigZag M30 sempre sem execução)
- `HappyGoldConfirmedResearchBotId`: `bot-13` (variante ZigZag com confirmação seletiva de regime, sempre sem execução)
- `HappyGoldRetestResearchBotId`: `bot-15` (v2 com reteste M5, regime direcional e gestão ATR/R, sempre sem execução)
- `HappyGoldCombinedPortfolioBotId`: `bot-16` (meta-portfólio da confirmação de regime com 7/6 100/100, sempre sem execução)
- `HistoryCacheBars`: `100000` somente no bot canônico, visando aproximadamente um ano de M5 quando a corretora disponibilizar essa profundidade
- `RefreshDeepHistoryOnInit`: `false` por padrão; ative somente para um bootstrap explícito dos 100 mil candles
- `SecondaryHistorySymbol`: `EURUSD`
- `SecondaryHistoryBotId`: `bot-eur-1`
- `RefreshSecondaryHistoryOnInit`: `false`; estratégias EURUSD estão arquivadas
- `LotusIngestApiKey`: valor de `DAYTRADE_INGEST_API_KEY`
- `EnableOrderExecution`: `false`

Depois de atualizar o EA, recompile-o e remova/anexe novamente ao gráfico. A versão atual converte
os horários do servidor da corretora para UTC antes de persistir candles e negócios; dados antigos
com deslocamento de horário não são reescritos automaticamente.

O MT5 e a API local usam a mesma rede privada de containers; por isso o EA usa `127.0.0.1` sem
expor a API para a rede externa.

Como `api` usa `network_mode: service:mt5`, não reinicie somente o container MT5: a API ficaria
presa ao namespace de rede anterior e o EA receberia `WebRequest 1001`. Depois de recompilar o EA,
reinicie nesta ordem e confirme a conectividade:

```bash
docker restart 2lotus-mt5-desktop
docker restart 2lotus-api
docker exec 2lotus-mt5-desktop curl --fail http://127.0.0.1:8000/health
```

O EA impõe internamente um piso de 100000 candles para o histórico canônico, mesmo quando um
gráfico antigo ainda preserva `HistoryCacheBars=2000` nos inputs salvos.

## Verificações antes do primeiro trade

```bash
docker exec 2lotus-mt5-desktop curl http://127.0.0.1:8000/health
```

O resultado deve indicar `"status":"ok"`. Após o fechamento de um trade demo, o EA envia um
`POST /api/trades` com a chave no header `X-2Lotus-Ingest-Key`; o painel 2Lotus passa a mostrar a
operação gravada no Supabase.

Durante shadow, confirme também nos logs que `bot-6`, `bot-7`, `bot-11`, `bot-12`, `bot-13`, `bot-15` e `bot-16` recebem HTTP 200. `strategy_signals`
recebe os candidatos quando cada setup ocorre e `paper_trades` mantém o variant `technical`;
o Bot 1 também acompanha `flow_confirmed`. As chaves de sinal e as consultas de posição são
segmentadas por bot. A execução real só pode ser avaliada depois da
amostra mínima e deve continuar com `EnableOrderExecution=false` até aprovação explícita.

O Bot 6 é uma experiência controlada: reutiliza o Stochastic Pullback, aceita somente vendas
com timestamp anterior às 18h UTC e mantém a liquidação diária padrão até 21h UTC. Seu status
`promising_not_live` autoriza apenas shadow/forward test, nunca execução automática.

O Bot 7 é outra experiência controlada: usa MME20/MME50 em H1 para a tendência longa,
MME9/MME21 em M15 para a tendência curta e pullback na MME9 do M5 como gatilho. As entradas
ficam limitadas a compras entre 13:00–15:59 UTC, exigem força mínima de 0,7 ATR(H1), usam alvo
único de 0,75R, stop técnico de 1,2 ATR e apenas 50% do risco padrão por operação. A duração
máxima continua em 60 minutos. Mesmo que o backtest supere 70%, o EA sempre consulta esse bot
com execução falsa.

O Bot 8 combina os componentes dos Bots 7 e 6 sem misturar seus gatilhos. O serviço avalia os
dois, dá prioridade ao Bot 7 quando houver conflito, aplica 75% do risco-base ao componente 7 e
25% ao componente 6, e mantém uma única posição. O replay limita o conjunto a duas entradas e
2R de perda por dia. O EA consulta o Bot 8 sempre com execução falsa durante o forward test.

O Bot 16 combina o portfólio 6/7 com risco 100/100 e o Happy Gold ZigZag. Seu replay usa 2% do
saldo por risco-base, aceita entradas entre 06:00–18:59 UTC e não possui limite diário de
operações. Permanecem ativos o limite de uma posição simultânea, o cooldown de 15 minutos e o
bloqueio ao atingir -2R no dia. O status `promising_not_live` mantém o bot somente em shadow.

O catálogo EUR/USD replica os sete perfis e parâmetros do catálogo XAU/USD. O propósito é medir
generalização; os resultados não devem ser interpretados como parâmetros otimizados para forex.
O EA envia o histórico profundo EURUSD/M5 uma única vez para `bot-eur-1`, e os demais bots EUR
reutilizam essa série. Depois da carga, dentro de `python-service`, execute
`python -m scripts.cache_backtests --symbol EURUSD --days 365` para atualizar as curvas exibidas
na tela inicial.

## Segurança e recuperação

- Nunca colocar o valor de `.env` em documentação, GitHub ou mensagens.
- A `service_role` do Supabase fica somente na API; o EA recebe apenas a chave de ingestão.
- Para parar o desktop MT5, use `docker stop 2lotus-mt5-desktop`.
- Para parar a API privada, use `docker stop 2lotus-api`.
- Para parar todo o harness, use `docker compose down`. Os dados persistidos em `.runtime`
  não são removidos.
- Para atualizar a Vercel, publique a partir de `/home/codexops/2Lotus/python-service`.
