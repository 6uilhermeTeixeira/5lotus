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
- `GET /compare`
- `GET /api/compare`
- `GET /api/bots/<id>/historical-replay?days=120`
- `POST /decision`

Perfis atuais, executados em paralelo:

- ativo base: `XAUUSD`
- timeframe base: `M5`
- Bot 1: `fimath_ema20_flow`
- Bot 2: `momentum_atr_breakout`
- Bot 3: `rsi_bollinger_reversion`
- Bot 4: `macd_trend_crossover`
- Bot 5: `stochastic_trend_pullback`
- Bot 6: `stochastic_sell_session` — variante shadow somente vendida, com entradas antes das 18h UTC
- Bot 7: `multitimeframe_trend_pullback` — tendência H1/M15, pullback M5 somente comprado entre 13h e 16h UTC, alvo de 0,75R e 50% do risco padrão, bloqueado em shadow
- Bots `bot-eur-1` a `bot-eur-7`: aplicação em `EURUSD/M5` dos mesmos sete perfis e parâmetros, sem otimização adicional para o novo ativo
- risco por operacao: `1%` da banca
- risco/retorno final: `2R`, com parcial de `50%` em `1R`

A Fimath usa MME20, pullback ou fora-dentro. O fluxo inferido da profundidade de mercado e
dos ticks do MT5 é normalizado por uma janela temporal e, na política padrão `veto`, só bloqueia
o setup quando livro e agressão apresentam forte contradição simultânea.

O Momentum ATR usa alinhamento MME20/MME50 e o rompimento do canal dos 12 candles anteriores.
O stop fica a `1,2 ATR(14)` e o fluxo não é usado como bloqueio, criando uma amostra independente
para comparação com a Fimath.

O RSI Bollinger busca reversão à média após uma excursão além das Bandas de Bollinger de 20
períodos. A entrada exige reentrada na banda, candle de reação e RSI(14) em região de exaustão;
o stop usa o extremo com buffer de ATR(14), a parcial fica na média de 20 e o alvo final em 2R.

O MACD Trend usa o cruzamento MACD(12,26,9) a favor da MME50. O stop fica a 1 ATR(14),
com parcial em 1R e alvo final em 2R, sem filtro de fluxo para manter a amostra independente.

O Stochastic Pullback usa a MME50 como direção e o cruzamento do Estocástico lento (14,3,3)
para detectar o fim de uma correção. O stop fica além dos três candles recentes, com buffer de ATR.

O replay histórico usa os candles persistidos no Supabase e executa o mesmo motor em ordem
cronológica, sempre com uma janela móvel de 60 candles. A página individual abre por padrão o
validação dos 120 dias anteriores ao último candle disponível e permite alternar para os dados
ao vivo/shadow. Os resultados do replay são calculados sob demanda e não são gravados nas tabelas
de trades reais ou paper trades.

O replay aprimorado separa geração de sinal e autorização por regime. Estratégias de tendência
só entram quando ADX(14) e EMA50/EMA200 em H1 confirmam tendência e direção; RSI Bollinger só
entra em range. Transição e volatilidade extrema ficam sem operação. A simulação também:

- usa o histórico canônico do `bot-1` para todos os bots XAUUSD/M5;
- restringe entradas à sessão UTC configurada e fecha posições no fim do dia;
- aplica bid/ask, spread, slippage e comissão configurável;
- limita operações diárias, perda diária e adiciona cooldown após loss;
- divide o resultado em janelas temporais mensais de 30 dias;
- mantém status `insufficient_history` até existirem pelo menos 90 dias avaliados.

Todo candidato técnico é gravado uma vez por candle com motivo, spread, `book_z`, `tick_z` e
`flow_score`. Dois paper tracks não sobrepostos são mantidos em paralelo:

- `technical`: todos os candidatos técnicos;
- `flow_confirmed`: apenas candidatos com confirmação forte do fluxo.

Por padrão o serviço opera em `shadow` e retorna `hold` até `DAYTRADE_FIMATH_MODE=live` e
`DAYTRADE_ENABLE_LIVE_DECISIONS=true` serem habilitados manualmente. Mesmo em live, a amostra
mínima configurada de paper trades encerrados continua sendo uma trava.

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

Variáveis de calibração:

```bash
DAYTRADE_FIMATH_FLOW_POLICY=veto
DAYTRADE_FIMATH_FLOW_WINDOW_SECONDS=300
DAYTRADE_CHART_CACHE_LIMIT=5000
DAYTRADE_FIMATH_FLOW_MIN_SAMPLES=30
DAYTRADE_FIMATH_FLOW_Z_THRESHOLD=1.0
DAYTRADE_FIMATH_MIN_CLOSED_PAPER_TRADES=30
DAYTRADE_BACKTEST_BALANCE=10000
DAYTRADE_BACKTEST_SPREAD_POINTS=10
DAYTRADE_BACKTEST_POINT_SIZE=0.01
DAYTRADE_BACKTEST_VALUE_PER_POINT_PER_LOT=1
DAYTRADE_BACKTEST_CANDLE_LIMIT=100000
DAYTRADE_BACKTEST_MARKET_DATA_BOT_ID=bot-1
DAYTRADE_BACKTEST_RISK_PER_TRADE_PCT=0.25
DAYTRADE_BACKTEST_SLIPPAGE_POINTS=2
DAYTRADE_BACKTEST_COMMISSION_PER_LOT=0
DAYTRADE_BACKTEST_SESSION_START_UTC=06:00
DAYTRADE_BACKTEST_SESSION_END_UTC=21:00
DAYTRADE_BACKTEST_MAX_TRADES_PER_DAY=4
DAYTRADE_BACKTEST_DAILY_LOSS_LIMIT_R=2
DAYTRADE_BACKTEST_COOLDOWN_BARS_AFTER_LOSS=3
DAYTRADE_BACKTEST_REGIME_ENABLED=true
DAYTRADE_BACKTEST_REGIME_TREND_ADX=25
DAYTRADE_BACKTEST_REGIME_RANGE_ADX=20
DAYTRADE_BACKTEST_REGIME_HIGH_VOLATILITY_PERCENTILE=90
DAYTRADE_BACKTEST_VALIDATION_FOLD_DAYS=5
```

Para preparar decisões executáveis após a validação dos paper tracks:

```bash
cd /home/codexops/2Lotus/python-service
DAYTRADE_FIMATH_MODE=live DAYTRADE_ENABLE_LIVE_DECISIONS=true ./run-local.sh
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
`/results` redireciona para o primeiro bot do catalogo. A página `/compare` apresenta os 14
testes (sete perfis em dois ativos) e atualiza seus indicadores pela API autenticada `/api/compare`.

A tela `/bots` alterna entre XAU/USD e EUR/USD e carrega `/api/equity-comparison?symbol=<ativo>&days=365`.
As curvas vêm de snapshots compactos em `backtest_snapshots`, gerados por
`python-service/scripts/cache_backtests.py`; candles permanecem canônicos em `market_candles`
(`bot-1` para XAUUSD e `bot-eur-1` para EURUSD).

O catálogo fica em `data/bots.json`. Para adicionar outro bot, inclua um novo item com `id`
único e um `results_file` dentro de `data/`; em seguida, crie esse JSON com a lista de trades.
O campo `description` é a sinopse usada na lista; `strategy_description` é o texto livre
exibido no card **Estratégia utilizada** da página de resultado. Use uma linha iniciada por
`- ` para cada tópico quando quiser que o card seja renderizado como uma lista. Assim, a tela
é reutilizada para novas estratégias sem código de interface. Se o campo não for informado,
o card usa `description`, preservando os bots já cadastrados. O primeiro bot demonstrativo usa
`data/bots/bot-1.json`.

```bash
DAYTRADE_DASHBOARD_PASSWORD=uma-senha-forte
DAYTRADE_SESSION_SECRET=um-segredo-aleatorio-com-pelo-menos-32-caracteres
```

Use `.env.example` apenas como referencia e configure essas variaveis tambem na Vercel. O cookie
de sessao e HTTP-only, assinado e expira em 12 horas por padrao.

## Resultados persistidos no Supabase

O projeto Supabase do 2Lotus usa as tabelas `bots` e `trade_results`, criadas pela migration
`supabase/migrations/20260720014500_create_daytrade_results.sql`. O painel consulta o banco quando
`DAYTRADE_RESULTS_STORE=SUPABASE` e as chaves `DAYTRADE_SUPABASE_URL` e
`DAYTRADE_SUPABASE_SERVICE_ROLE_KEY` estao configuradas.

O MT5 deve registrar cada trade fechado ou atualizado em `POST /api/trades`, enviando a chave no
header `X-2Lotus-Ingest-Key`. O payload possui `bot_id` e `trade`, com o mesmo formato de trade
documentado abaixo. A chave de ingestao e validada no servidor; a `service_role` nunca e exposta
ao navegador ou ao MT5.

As tabelas `strategy_signals` e `paper_trades` são privadas e acessadas somente pela API com
`service_role`. A migration `20260731090000_add_strategy_candidate_telemetry.sql` adiciona a
telemetria dos candidatos e a chave composta `(signal_key, variant)` dos paper tracks.
A migration `20260731093000_add_bot_2_momentum_atr.sql` cadastra o segundo perfil no catálogo.
A migration `20260731100000_add_bot_3_rsi_bollinger.sql` cadastra o terceiro perfil e reafirma
RLS e a ausência de privilégios para `anon`/`authenticated` no catálogo.
A migration `20260731103000_add_bot_4_macd_trend.sql` cadastra o quarto perfil com as mesmas
garantias de acesso privado ao catálogo.
A migration `20260731110000_add_bot_5_stochastic_pullback.sql` cadastra o quinto perfil sem
alterar o formato das tabelas existentes.

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
