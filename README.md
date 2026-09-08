# 2Lotus

Laboratório privado de estratégias XAUUSD/M5 com execução MetaTrader 5, motor Python, persistência Supabase e portal Vercel. A operação permanece integralmente em `shadow`; nenhuma estratégia está autorizada a enviar ordens reais.

## Catálogo selecionado

- **ZigZag Scalper**
  - `core-zigzag` — rompimento causal M30 original.
  - `core-zigzag-v2` — variante Tick Estrutural, sem filtro de range, com risco normalizado e gestão de 60 segundos.
  - `core-zigzag-v3` — variante adaptativa: V1 em volatilidade normal e V2 estrutural em expansão do range M5.
- **Stochastic Sell**
  - `core-stochastic` — baseline com limiar 65, corte às 18:00 UTC e alvo 2R.
  - `core-stochastic-v2` — variante shadow seletiva com limiar 85, corte às 15:00 UTC e alvo 1,25R.
  - `core-stochastic-v3` — regime adaptativo shadow com geometria V2, corte às 13:00 UTC e veto ao regime H1 vendedor fraco.
- **Tendência Multitemporal**
  - `core-multitimeframe` — baseline com força H1 de 0,7 ATR e alvo 0,75R.
  - `core-multitimeframe-v2` — variante shadow com força H1 de 0,5 ATR, alvo 1,25R e duração máxima de 30 minutos.
  - `core-multitimeframe-v3` — variante shadow adaptativa: V2 em range/transição, V1 em tendência/alta volatilidade e bloqueio de tendência H1 vendedora.
- **Combinação das 3**
  - `core-combined-v3` — união shadow das V3 de ZigZag, Stochastic Sell e Tendência Multitemporal, com posição e risco compartilhados.
- **Combinação das 3** — `core-portfolio`.

A V2 do ZigZag permanece exclusivamente em `shadow`: os resultados de holdout justificam acompanhamento, mas ainda não autorizam execução real.

Estratégias rejeitadas e arquivadas foram exportadas para backup de auditoria e removidas do catálogo operacional.

## Arquitetura

```text
MT5 / EA MQL5
  -> POST /decision, /api/candles e /api/trades
Python / FastAPI
  -> regras, risco shadow, idempotência, paper tracking e replay
Supabase
  -> market_history, ticks, sinais, paper trades, snapshots e saúde
Vercel
  -> catálogo, comparação, resultados, simulador e operações
```

O histórico pertence ao mercado (`symbol + timeframe + timestamp`) e não a um bot. Replays anuais são gerados pelo comando `scripts/cache_backtests.py`; requisições web apenas leem snapshots versionados.

## Validação local

```bash
cd python-service
.venv/bin/python -m unittest discover -s tests
.venv/bin/coverage run -m unittest discover -s tests && .venv/bin/coverage report
.venv/bin/ruff check app tests
PATH="$PWD/.venv/bin:$PATH" vercel build --prod --yes
```

Consulte `docs/architecture.md`, `docs/http-contract.md` e `docs/2lotus-operational-setup.md` para operação e contratos.
A coleta de ticks para reconstruções de estratégias de segundos está em `docs/tick-research.md`.

`GET /health` verifica somente o processo. `GET /ready` confirma também configuração e acesso ao
Supabase. Métricas diagnósticas agregadas ficam em `GET /api/metrics`, protegido pela sessão do portal.

## Divisão entre os três Lotus

- **1lotus** publica releases Parquet imutáveis em `/home/codexops/lotus-data`.
- **2Lotus** é o laboratório de estratégias e lê essas releases em modo somente leitura.
- **3lotus** recebe apenas bundles de estratégias aprovados manualmente e acompanha a operação.

Validar o dataset atualmente publicado:

```bash
cd python-service
PYTHONPATH=. .venv/bin/python scripts/inspect_local_dataset.py --verify-hashes
```

Todo replay deve registrar a versão mostrada em `releases/CURRENT`. O downloader Dukascopy deste
repositório fica legado durante a transição e não deve ser iniciado para novas coletas.
