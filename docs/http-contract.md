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
  "service": "mt5-daytrade-strategy-service",
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

Nesta fase, o servico trabalha com estes pressupostos:

- ativo base: `XAUUSD`
- timeframe base: `M5`
- perfil de estrategia: `price_action_breakout_pullback`
- risco maximo por operacao: `5%` da banca
- gatilho: `breakout + pullback + ignition candle`
- stop: atras do ultimo topo/fundo relevante
- risco/retorno minimo: `1:1.5`
- o servico pode calcular `suggested_size`
- a decisao final continua conservadora por padrao enquanto `DAYTRADE_ENABLE_LIVE_DECISIONS` nao estiver ativo

Isso e intencional:

- a deteccao automatica do setup ja esta no servico Python, mas o fluxo completo ainda precisa ser validado dentro do terminal demo
- o sizing e o risco ja podem ser validados desde agora
- a execucao automatica no terminal continua bloqueada ate estabilizar o fluxo no demo

## Travas de execucao

Para disparar ordens automaticamente, as duas travas precisam estar ligadas:

1. no servico Python:
   `DAYTRADE_ENABLE_LIVE_DECISIONS=true`
2. no EA:
   `EnableOrderExecution=true`

## Fluxo de teste

O roteiro operacional completo de teste em demo esta em:

- `docs/demo-test-playbook.md`
