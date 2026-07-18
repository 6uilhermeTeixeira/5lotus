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
- `run-local.sh`

## Como rodar

```bash
cd /home/codexops/workspace/daytrade/python-service
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DAYTRADE_ENABLE_LIVE_DECISIONS=false ./run-local.sh
```

Para habilitar decisoes executaveis:

```bash
cd /home/codexops/workspace/daytrade/python-service
DAYTRADE_ENABLE_LIVE_DECISIONS=true ./run-local.sh
```

## Como testar

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/config
curl -X POST http://127.0.0.1:8000/decision \
  -H 'Content-Type: application/json' \
  --data @sample-decision.json
```

## Observacao operacional

Mesmo com o servico liberando `buy` ou `sell`, o EA do MT5 ainda precisa estar com `EnableOrderExecution=true` para mandar a ordem.
