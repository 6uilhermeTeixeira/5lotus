# 2Lotus

Laboratório privado de estratégias XAUUSD/M5 com execução MetaTrader 5, motor Python, persistência Supabase e portal Vercel. A operação permanece integralmente em `shadow`; nenhuma estratégia está autorizada a enviar ordens reais.

## Catálogo selecionado

- `bot-6` — Stochastic Sell 18 UTC
- `bot-7` — Tendência Multitemporal
- `bot-11` — Portfólio 7/6 · 100/100
- `bot-12` — Happy Gold ZigZag Scalper
- `bot-13` — Happy Gold ZigZag · Confirmação de Regime
- `bot-16` — Happy Gold + Portfólio 7/6 · 100/100

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
