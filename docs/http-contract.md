# Contrato HTTP inicial

## Objetivo

Definir o contrato minimo entre o `Expert Advisor MQL5` e o `Python strategy service` para o setup inicial de `XAUUSD` em `M5`.

Observacao:

- o servico precisa de pelo menos `23` candles para validar o setup automatico
- o arquivo real de exemplo esta em `python-service/sample-decision.json`

## Endpoint de saude

- `GET /health`

Resposta:

```json
{
  "status": "ok",
  "service": "2lotus-strategy-service",
  "timestamp_utc": "2026-07-18T01:00:00Z"
}
```

## Endpoint de decisao

- `POST /decision`

Payload de referencia:

```json
{
  "request_id": "sample-001",
  "timestamp_utc": "2026-07-18T02:00:00Z",
  "symbol": "XAUUSD",
  "timeframe": "M5",
  "bid": 3360.8,
  "ask": 3361.0,
  "spread_points": 2.0,
  "point_size": 0.1,
  "value_per_point_per_lot": 1.0,
  "candles": [
    { "timestamp_utc": "2026-07-18T02:15:00Z", "open": 3355.0, "high": 3358.6, "low": 3354.9, "close": 3358.3, "volume": 260 },
    { "timestamp_utc": "2026-07-18T02:20:00Z", "open": 3358.3, "high": 3358.5, "low": 3354.9, "close": 3355.2, "volume": 120 },
    { "timestamp_utc": "2026-07-18T02:25:00Z", "open": 3355.2, "high": 3361.2, "low": 3355.0, "close": 3360.9, "volume": 280 }
  ],
  "positions": [],
  "account": {
    "balance": 10000.0,
    "equity": 10000.0,
    "margin_free": 10000.0,
    "leverage": 20
  },
  "indicators": {}
}
```

No exemplo acima a lista de `candles` foi truncada so para leitura. O arquivo de amostra no repositorio contem a serie completa usada no teste local.

Resposta minima:

```json
{
  "action": "hold",
  "reason": "live_decisions_disabled",
  "size": 0.0,
  "risk_amount": 500.0,
  "entry_price": 3361.0,
  "stop_loss_price": 3350.1785714285716,
  "take_profit_price": 3377.2321428571427,
  "stop_loss_points": 108.21,
  "take_profit_points": 162.32,
  "risk_checks": [
    {
      "name": "symbol_match",
      "passed": true,
      "detail": "symbol=XAUUSD expected=XAUUSD"
    },
    {
      "name": "timeframe_match",
      "passed": true,
      "detail": "timeframe=M5 expected=M5"
    },
    {
      "name": "spread_limit",
      "passed": true,
      "detail": "spread=2.0 max=3.0"
    },
    {
      "name": "risk_per_trade_limit",
      "passed": true,
      "detail": "risk_pct=5.0"
    }
  ],
  "metadata": {
    "symbol": "XAUUSD",
    "timeframe": "M5",
    "strategy_profile": "price_action_breakout_pullback",
    "suggested_action": "buy",
    "suggested_size": 4.62,
    "risk_per_trade_pct": 5.0,
    "rr_ratio": 1.5,
    "min_risk_reward": 1.5,
    "stop_reference": "fractal_5_plus_atr14"
  }
}
```

## Catálogo de estratégias

- `GET /api/bots` retorna somente estratégias ativas.
- `GET /api/bots?archived=true` retorna somente estratégias arquivadas.
- `GET /api/bots/{bot_id}/results`, `/chart` e `/historical-replay` aceitam IDs ativos ou arquivados para preservar a consulta histórica.
- `POST /decision`, `POST /api/trades` e `POST /api/candles` rejeitam estratégias arquivadas, pois resolvem exclusivamente o catálogo ativo.
- O campo `active` explicita o estado operacional. O campo `name` contém apenas o título público; o identificador `bot-N` permanece no campo `id`.

## Decisao atual

O serviço trabalha com estes pressupostos:

- ativos de pesquisa: `XAUUSD` e `EURUSD`
- timeframe base: `M5`
- perfis ativos: Bot 11 usa `portfolio_6_7_100_100` e Bot 16 usa `happy_gold_portfolio_100_100`; os demais ativos são Bots 6, 7, 12, 13 e 15, todos em XAUUSD/M5
- no Bot 7, `risk_amount`, `suggested_size` e `effective_risk_pct` já incorporam o multiplicador experimental de risco `0,5`; o alvo é `0,75R` e somente sinais de compra entre 13:00 e 15:59 UTC são candidatos
- no Bot 8, esses campos incorporam a alocação do componente selecionado: `0,75` para o Bot 7 e `0,25` para o Bot 6; `portfolio_component`, `portfolio_weight_pct` e a prioridade aplicada são retornados em `metadata`
- no Bot 9, `adaptive_component_health_json` registra a janela causal de 120 dias e `adaptive_active_component` permanece congelado durante o dia UTC; somente o componente selecionado recebe 100% do risco-base do candidato, sempre em shadow
- nos Bots 10 e 11, `portfolio_risk_state_json` registra operações e resultado do dia, `portfolio_regime*` comprova o filtro vendedor do Bot 6 e `portfolio_weight_pct` retorna respectivamente 75/50 ou 100/100 conforme o componente
- no Bot 12, `signal_timeframe=M30`, `fixed_stop_points=240`, `fixed_target_points=1000`, `suggested_size=0.10`, `break_even_trigger_points=40`, `trailing_activation_points=120` e `trailing_distance_points=60` documentam a assinatura reconstruída; `experimental_shadow_lock=true` impede execução
- no Bot 13, `selective_regime_confirmation=true` preserva o Bot 12 em `range/trend`; `zigzag_close_confirmed` e `zigzag_direction_aligned` precisam ser verdadeiros em `transition/high_volatility`
- no Bot 15, `entry_model=breakout_retest_rejection`, `target_r=2`, gestão dinâmica em pontos e `max_holding_bars=12` descrevem a v2; `experimental_shadow_lock=true` impede execução
- no Bot 16, `combined_component`, `combined_priority` e os flags de candidato identificam a fonte selecionada; conflitos ficam em `hold` e o risco total nunca ultrapassa 100% do risco-base
- risco máximo por operação: `1%` da banca
- gatilho: pullback/rejeição da MME20 ou padrão fora-dentro
- stop: estrutura da rejeição com buffer de ATR(14)
- parcial de 50% em 1R, breakeven e alvo final em 2R
- o servico pode calcular `suggested_size`
- fluxo padrão `veto`: somente forte contradição simultânea de livro e ticks bloqueia
- a decisão continua em `hold` enquanto shadow/live e a amostra mínima não forem liberados

Quando existe candidato, `metadata` inclui:

- `candidate`, `candle_timestamp_utc`, `suggested_action` e `setup_type`
- `flow_status`, `flow_ready`, `flow_confirmed` e `flow_contradicted`
- `book_z`, `tick_z` e `flow_score` quando a janela está aquecida
- MME20, ATR(14), tamanho sugerido e política aplicada
- no Momentum ATR, MME50 e nível de rompimento
- no RSI Bollinger, RSI(14), banda superior, banda inferior e média de 20 períodos
- no MACD Trend, linha MACD, linha de sinal, histograma e MME50
- no Stochastic Pullback, %K, %D e MME50

## Travas de execucao

Para disparar ordens automaticamente, todas as travas precisam estar liberadas:

1. no servico Python:
   `DAYTRADE_FIMATH_MODE=live`
2. no servico Python:
   `DAYTRADE_ENABLE_LIVE_DECISIONS=true`
3. no paper trading:
   amostra mínima encerrada no variant exigido pela política
4. no EA:
   `EnableOrderExecution=true`

## Fluxo de teste

O roteiro operacional completo de teste em demo esta em:

- `docs/demo-test-playbook.md`

## Replay histórico autenticado

- `GET /api/bots/{bot_id}/historical-replay?days=120`
- `days` aceita valores de `1` a `30`
- requer a mesma sessão autenticada do portal
- requer candles em `market_candles` e `DAYTRADE_RESULTS_STORE=SUPABASE`

O período termina no fechamento do candle mais recente disponível. A resposta inclui candles,
operações simuladas, contagem de candidatos, resumo de performance, PnL diário e as premissas do
cálculo. O replay não persiste registros e nunca aciona o endpoint de execução do MT5.

Regras de simulação:

- cada decisão recebe no máximo os 60 candles que estariam disponíveis naquele instante;
- uma estratégia mantém no máximo uma posição simulada aberta por vez;
- parcial em 1R move o stop do saldo para breakeven e o alvo final permanece em 2R;
- quando o OHLC toca stop e alvo no mesmo candle, o stop vence;
- entrada, spread, slippage e custos são aproximações configuráveis;
- para `fimath_ema20_flow`, apenas o gatilho técnico pode ser reconstruído porque OHLC não contém livro nem sequência de ticks.
- todos os bots XAUUSD/M5 reutilizam o histórico canônico do Bot 1, evitando coberturas diferentes para o mesmo mercado;
- todos os bots EURUSD/M5 reutilizam o histórico canônico do `bot-eur-1`; o ponto do replay é `0,00001`, enquanto XAUUSD mantém `0,01`;
- `GET /api/equity-comparison?symbol=XAUUSD|EURUSD&days=365` retorna uma curva acumulada por estratégia a partir de snapshots previamente calculados;
- entradas fora da sessão configurada são bloqueadas e qualquer posição restante é fechada no fim do dia;
- compras usam ask na entrada e bid na saída; vendas usam bid na entrada e ask na saída;
- slippage e comissão são aplicados aos fills;
- estratégias de tendência exigem H1 em tendência e lado alinhado; reversão à média exige regime de range;
- a resposta inclui expectativa em R, drawdown em R, bloqueios, regimes e janelas temporais de validação;
- menos de 90 dias resulta em `validation_status=insufficient_history`, mesmo que o PnL do mês seja positivo;
- a estabilidade usa janelas de 30 dias por padrão, adequadas à frequência observada das estratégias.
