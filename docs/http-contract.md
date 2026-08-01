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

## Decisao atual

O serviço trabalha com estes pressupostos:

- ativo base: `XAUUSD`
- timeframe base: `M5`
- perfis de estratégia: `fimath_ema20_flow` no Bot 1, `momentum_atr_breakout` no Bot 2, `rsi_bollinger_reversion` no Bot 3, `macd_trend_crossover` no Bot 4, `stochastic_trend_pullback` no Bot 5, `stochastic_sell_session` no Bot 6 e `multitimeframe_trend_pullback` no Bot 7
- no Bot 7, `risk_amount`, `suggested_size` e `effective_risk_pct` já incorporam o multiplicador experimental de risco `0,5`; o alvo é `0,75R` e somente sinais de compra entre 13:00 e 15:59 UTC são candidatos
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
- entradas fora da sessão configurada são bloqueadas e qualquer posição restante é fechada no fim do dia;
- compras usam ask na entrada e bid na saída; vendas usam bid na entrada e ask na saída;
- slippage e comissão são aplicados aos fills;
- estratégias de tendência exigem H1 em tendência e lado alinhado; reversão à média exige regime de range;
- a resposta inclui expectativa em R, drawdown em R, bloqueios, regimes e janelas temporais de validação;
- menos de 90 dias resulta em `validation_status=insufficient_history`, mesmo que o PnL do mês seja positivo;
- a estabilidade usa janelas de 30 dias por padrão, adequadas à frequência observada das estratégias.
