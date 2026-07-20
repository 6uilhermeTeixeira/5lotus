# Python Strategy Service

Esta pasta vai conter:

- motor de estrategia
- motor de risco
- API local para integracao com o MT5
- logs e testes da camada Python

## Implementacao atual

Foi criado um servico minimo com:

- `GET /health`
- `GET /config`
- `GET /api/results`
- `GET /results`
- `GET /login`
- `GET /bots`
- `POST /decision`

Perfil atual:

- ativo base: `XAUUSD`
- timeframe base: `M5`
- estrategia base: `price_action_breakout_pullback`
- risco por operacao: `5%` da banca
- risco/retorno minimo: `1.5`

Por seguranca, `POST /decision` ainda pode retornar `hold` mesmo quando o setup estiver confirmado, enquanto `DAYTRADE_ENABLE_LIVE_DECISIONS` estiver desligado.

## Estrutura

- `app/main.py`
- `app/config.py`
- `app/schemas.py`
- `app/strategy.py`
- `requirements.txt`
- `sample-decision.json`
- `data/trade-results.json`
- `run-local.sh`

## Como rodar

```bash
cd /home/codexops/2Lotus/python-service
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DAYTRADE_ENABLE_LIVE_DECISIONS=false ./run-local.sh
```

Para habilitar decisoes executaveis:

```bash
cd /home/codexops/2Lotus/python-service
DAYTRADE_ENABLE_LIVE_DECISIONS=true ./run-local.sh
```

## Como testar

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/config
curl http://127.0.0.1:8000/api/results
curl -X POST http://127.0.0.1:8000/decision \
  -H 'Content-Type: application/json' \
  --data @sample-decision.json
```

Portal de resultados:

```bash
DAYTRADE_DASHBOARD_PASSWORD=uma-senha-forte \
DAYTRADE_SESSION_SECRET=um-segredo-aleatorio-com-pelo-menos-32-caracteres \
./run-local.sh

open http://127.0.0.1:8000/login
```

## Acompanhamento de resultado

O servico expoe um portal protegido por senha em `/login`. Depois do acesso, `/bots` lista os
testes disponiveis e cada bot possui uma pagina individual em `/bots/<id>`. A rota antiga
`/results` redireciona para o primeiro bot do catalogo.

O catalogo fica em `data/bots.json`. Para adicionar outro bot, inclua um novo item com `id`
unico e um `results_file` dentro de `data/`; em seguida, crie esse JSON com a lista de trades.
O primeiro bot demonstrativo usa `data/bots/bot-1.json`.

```bash
DAYTRADE_DASHBOARD_PASSWORD=uma-senha-forte
DAYTRADE_SESSION_SECRET=um-segredo-aleatorio-com-pelo-menos-32-caracteres
```

Use `.env.example` apenas como referencia e configure essas variaveis tambem na Vercel. O cookie
de sessao e HTTP-only, assinado e expira em 12 horas por padrao.

## Resultados persistidos no Supabase

O projeto Supabase do Daytrade usa as tabelas `bots` e `trade_results`, criadas pela migration
`supabase/migrations/20260720014500_create_daytrade_results.sql`. O painel consulta o banco quando
`DAYTRADE_RESULTS_STORE=SUPABASE` e as chaves `DAYTRADE_SUPABASE_URL` e
`DAYTRADE_SUPABASE_SERVICE_ROLE_KEY` estao configuradas.

O MT5 deve registrar cada trade fechado ou atualizado em `POST /api/trades`, enviando a chave no
header `X-2Lotus-Ingest-Key`. O payload possui `bot_id` e `trade`, com o mesmo formato de trade
documentado abaixo. A chave de ingestao e validada no servidor; a `service_role` nunca e exposta
ao navegador ou ao MT5.

Formato esperado de cada trade no JSON:

```json
[
  {
    "trade_id": "mt5-20260718-001",
    "symbol": "XAUUSD",
    "timeframe": "M5",
    "setup": "price_action_breakout_pullback",
    "side": "buy",
    "opened_at_utc": "2026-07-18T13:10:00Z",
    "closed_at_utc": "2026-07-18T13:42:00Z",
    "volume_lots": 1.25,
    "entry_price": 3361.0,
    "exit_price": 3377.23,
    "stop_loss_price": 3350.18,
    "take_profit_price": 3377.23,
    "risk_amount": 500.0,
    "gross_pnl": 750.0,
    "fees": 12.0,
    "net_pnl": 738.0,
    "rr_realized": 1.48,
    "note": "trade demo"
  }
]
```

Com isso a pagina calcula:

- PnL liquido
- lucro e perda brutos
- quantidade de trades fechados
- posicoes ainda abertas
- win rate
- profit factor
- RR medio
- melhor e pior trade
- PnL diario
- lista de trades recentes

O texto no topo da pagina indica o horario do ultimo trade registrado, calculado pelos dados do
JSON; ele nao usa a data tecnica do arquivo no ambiente da Vercel.

## Observacao operacional

Mesmo com o servico liberando `buy` ou `sell`, o EA do MT5 ainda precisa estar com `EnableOrderExecution=true` para mandar a ordem.
