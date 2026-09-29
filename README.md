# 5lotus Research

Ambiente privado de pesquisa, dados históricos, backtests e desenvolvimento de novas estratégias. O serviço local usa `127.0.0.1:7775`; nenhuma configuração deste repositório autoriza execução real.

Laboratório privado de estratégias XAUUSD/M5 com coleta MetaTrader 5, motor Python, persistência Supabase e portal de pesquisa. A operação permanece integralmente em `shadow`; nenhuma estratégia está autorizada a enviar ordens reais. Estratégias aprovadas são portadas por revisão para o 4lotus, que produz os bundles consumidos pelo 2lotus.

Na implantação atual, este serviço também hospeda provisoriamente o Live Core e mantém a conta demo
já registrada. O estado-alvo é conservar aqui somente laboratório/forward demo e transferir o Live
Core para o serviço dedicado `live-core`, onde será conectada a conta real após o preflight.

## Catálogo selecionado

- **ZigZag Scalper**
  - **V1 — Gatilhos:** `core-zigzag` (estrutural M30), `core-zigzag-v12` (microreteste), `core-zigzag-v13` (fechamento M30) e `core-zigzag-v2` (tick estrutural).
  - **V2 — Roteadores de gatilho:** `core-zigzag-v3` (regime) e `core-zigzag-v5` (composto).
  - **V3 — Filtros temporais:** `core-zigzag-v4` (calendário/direção) e `core-zigzag-v8` (calendário mensal).
  - **V4 — Roteador temporal:** `core-zigzag-v72` (semanal).
  - **V5 — Filtros contextuais:** `core-zigzag-v6` (vendas) e `core-zigzag-v7` (direcional).

A genealogia completa e as categorias futuras V6/V7 estão em
[`docs/zigzag-scalper-taxonomy.md`](docs/zigzag-scalper-taxonomy.md).
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
A inclusão de novos perfis deve seguir `docs/strategy-registry.md`; listas paralelas de estratégias
em módulos web ou de replay não são fontes de verdade.
As fronteiras de diretório e a sequência de extrações estão em `docs/project-organization.md`.
A coleta de ticks para reconstruções de estratégias de segundos está em `docs/tick-research.md`.
O retrato técnico validado e o PRD de melhorias ficam em `docs/current-state.md` e
`docs/PRD-improvements.md`.

`GET /health` verifica somente o processo. `GET /ready` confirma também configuração e acesso ao
Supabase. Métricas diagnósticas agregadas ficam em `GET /api/metrics`, protegido pela sessão do portal.

## Divisão entre os três Lotus

- **2Lotus** contém atualmente o pipeline que publica releases Parquet imutáveis em
  `/home/codexops/lotus-data` e também é o laboratório que as consome em modo somente leitura.
- **2Lotus Live Core** (`2lotus-live-core`, diretório local `1lotus`) recebe bundles aprovados e
  concentra a operação protegida.
- **institucional-2lotus** (diretório local `3lotus`) é o site institucional; não participa do fluxo
  de dados, decisão ou execução.

Validar o dataset atualmente publicado:

```bash
cd python-service
PYTHONPATH=. .venv/bin/python scripts/inspect_local_dataset.py --verify-hashes
```

Todo replay deve registrar a versão mostrada em `releases/CURRENT`. Até a extração do pipeline para
um repositório próprio, o downloader/publicador deste repositório é a implementação ativa e deve ser
operado somente pelos scripts documentados.
