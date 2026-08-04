# Arquitetura operacional

## Princípios

- MT5/MQL5 executa coleta e, futuramente, ordens; Python decide e audita.
- Todas as seis estratégias permanecem em shadow e falham fechadas.
- OHLCV pertence ao mercado, não ao catálogo de estratégias.
- Replays são causais, versionados e produzidos fora das requisições web.
- Supabase usa RLS sem privilégios para `anon` ou `authenticated`; somente o backend usa service role.

## Componentes e fluxo

```mermaid
flowchart LR
  MT5[MT5 + SyncLeadBridgeEA] -->|chave de ingestão| API[FastAPI]
  API --> Engine[Motor de estratégias]
  Engine --> DB[(Supabase)]
  DB --> History[market_history]
  DB --> Paper[signals + paper_trades]
  DB --> Cache[backtest_snapshots]
  DB --> Ops[bot_runtime_status]
  Portal[Portal autenticado] --> API
  Job[cache_backtests.py] --> Engine
  Job --> Cache
```

O EA consulta apenas `bot-6`, `bot-7`, `bot-11`, `bot-12`, `bot-13` e `bot-16`. A decisão grava o histórico canônico por símbolo/timeframe, avança paper trades e atualiza o heartbeat operacional.

## Persistência

| Tabela | Responsabilidade |
|---|---|
| `bots` | seis perfis selecionados e seus textos públicos |
| `market_history` | OHLCV canônico por mercado e timestamp |
| `strategy_signals` | candidatos deduplicados e resposta do motor |
| `paper_trades` | acompanhamento técnico em shadow |
| `trade_results` | negócios encerrados reportados pelo MT5 |
| `backtest_snapshots` | replay compacto, versão e fingerprint das configurações |
| `bot_runtime_status` | último heartbeat, candle, resposta e latência |

## Portal

- `/bots`: catálogo e curvas anuais.
- `/compare`: resultados shadow lado a lado.
- `/bots/{id}`: replay e eventos da estratégia.
- `/growth-simulator`: risco fixo ou faixas permanentes de redução.
- `/operations`: heartbeat, atraso de mercado e validade dos snapshots.

## Segurança e operação

Dashboard e APIs de leitura exigem cookie assinado. Decisão e ingestão usam uma chave separada em header. `/health` é público e não expõe configuração; `/config` exige sessão. Execução continua bloqueada por flags no Python, trava experimental dos perfis e `EnableOrderExecution=false` no EA.
