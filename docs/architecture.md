# Arquitetura operacional

## Princípios

- MT5/MQL5 executa coleta e, futuramente, ordens; Python decide e audita.
- As três estratégias V3 e a combinação V3 permanecem em shadow e falham fechadas.
- OHLCV pertence ao mercado, não ao catálogo de estratégias.
- Replays são causais, versionados e produzidos fora das requisições web.
- Supabase usa RLS sem privilégios para `anon` ou `authenticated`; somente o backend usa service role.

## Componentes e fluxo

```mermaid
flowchart LR
  MT5[MT5 + SyncLeadBridgeEA] -->|chave de ingestão| API[FastAPI]
  API --> Engine[Motor de estratégias]
  API --> Telemetry[logs JSON + métricas]
  Engine --> DB[(Supabase)]
  DB --> History[market_history]
  DB --> Paper[signals + paper_trades]
  DB --> Cache[backtest_snapshots]
  DB --> Ops[bot_runtime_status]
  Portal[Portal autenticado] --> API
  Job[cache_backtests.py] --> Engine
  Job --> Cache
```

O EA consulta `core-zigzag-v3`, `core-stochastic-v3`, `core-multitimeframe-v3` e
`core-combined-v3`. A decisão grava o histórico canônico por símbolo/timeframe, avança paper trades e atualiza o heartbeat operacional.
Cada chamada carrega `request_id` como chave de correlação. Respostas concluídas são persistidas por
`bot_id + request_id`, tornando retries posteriores idempotentes.

O executor MQL5 atual aceita uma única decisão por consulta. Portanto, a combinação V3, que retorna
`parallel_candidates`, ainda não deve ser escolhida em `ExecutionBotId`. Também não se deve executar
simultaneamente a combinação e as três estratégias individuais, pois isso duplicaria exposição.

## Persistência

| Tabela | Responsabilidade |
|---|---|
| `bots` | quatro perfis V3 selecionados e seus textos públicos |
| `market_history` | OHLCV canônico por mercado e timestamp |
| `market_ticks` | Bid/Ask bruto por broker e milissegundo para pesquisa shadow |
| `strategy_signals` | candidatos deduplicados e resposta do motor |
| `paper_trades` | acompanhamento técnico em shadow |
| `trade_results` | negócios encerrados reportados pelo MT5 |
| `backtest_snapshots` | replay compacto, versão e fingerprint das configurações |
| `bot_runtime_status` | último heartbeat, candle, resposta e latência |
| `decision_requests` | resposta final por requisição, usada para auditoria e idempotência |

## Portal

- `/bots`: catálogo e curvas anuais.
- `/compare`: resultados shadow lado a lado.
- `/bots/{id}`: replay e eventos da estratégia.
- `/growth-simulator`: risco fixo ou faixas permanentes de redução.
- `/operations`: heartbeat, atraso de mercado e validade dos snapshots.
- `/health`: liveness do processo; não consulta dependências.
- `/ready`: readiness da configuração e do Supabase.
- `/api/metrics`: contadores e latências agregadas, disponível somente com sessão.

## Segurança e operação

Dashboard e APIs de leitura exigem cookie assinado. Decisão e ingestão usam uma chave separada em header. `/health` é público e não expõe configuração; `/config` exige sessão. Execução continua bloqueada por flags no Python, trava experimental dos perfis e `EnableOrderExecution=false` no EA.
Login e ingestão têm limites por processo. Operações autenticadas rejeitam origens cruzadas. O portal
escapa valores dinâmicos antes de inseri-los em HTML e envia uma política CSP restritiva.

Os logs de decisão são JSON e usam `request_id`, etapa, estado, duração e código de erro normalizado.
Credenciais e payloads completos não são registrados. As métricas em memória são por instância; a
agregação entre instâncias deve ser feita pelo coletor de telemetria da plataforma.
