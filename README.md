# 2Lotus

Projeto 2Lotus para desenvolver um bot de daytrade com execucao na plataforma MetaTrader 5.

Status atual: runtime MT5 em Docker validado, desktop remoto local pronto para concluir a primeira instalacao do terminal, e esqueleto inicial `MT5 -> Python service` implementado.

## Objetivo

Construir uma stack de trading automatizado com:

- execucao de ordens no MT5
- motor de estrategia separado da camada de execucao
- controles de risco antes de qualquer ordem
- trilha de auditoria de sinais, ordens, posicoes e erros
- ambiente de simulacao e validacao antes de operar conta real

## Decisao inicial

Para este servidor Linux, a opcao recomendada e:

1. `MT5 + EA MQL5` como camada de execucao
2. `Python service` como motor de estrategia, risco e observabilidade
3. comunicacao local entre MT5 e Python por HTTP local

Motivo: a execucao nativa do MT5 depende de ambiente Windows/Wine, enquanto o servidor ja esta pronto para Python no Linux. Isso reduz acoplamento e deixa a execucao mais proxima do runtime suportado pelo MT5.

## Perfil operacional inicial

- ativo: `XAUUSD`
- timeframe: `M5`
- classe de estrategia: `price action breakout + pullback`
- risco maximo por operacao: `5%` da banca
- risco/retorno minimo: `1:1.5`
- execucao automatica ainda protegida por flag no servico Python

## Estado atual da automacao

Ja existe implementacao para:

- detectar o setup automaticamente a partir de candles M5
- calcular stop por fractal `5` com buffer de `1 ATR(14)`
- calcular alvo com RR minimo `1.5`
- calcular tamanho de posicao pelo risco de `5%`
- permitir envio automatico da ordem pelo EA quando as travas forem habilitadas
- expor uma pagina separada de acompanhamento de resultados em `python-service` via `GET /results`
- validar as estratégias candle a candle nos últimos 120 dias disponíveis e apresentar entradas, saídas e métricas simuladas sem depender do mercado aberto
- filtrar sinais por regime H1, sessão e limites diários, com custos de execução e validação temporal explícitos
- acompanhar uma variante experimental Stochastic somente vendida antes das 18h UTC, isolada em shadow como Bot 6
- acompanhar o Bot 7 multitemporal em shadow, com tendência H1, confirmação M15, gatilho M5, somente compras entre 13h e 16h UTC e metade do risco padrão por operação
- executar as mesmas sete estratégias em EURUSD/M5 sobre um histórico canônico de um ano, sem recalibração por ativo
- alternar XAU/USD e EUR/USD na tela inicial e comparar as curvas de PnL acumulado dos sete bots em um único gráfico

## Estrutura inicial

- `docs/` documentacao do projeto
- `mt5/` artefatos da camada MT5/MQL5
- `python-service/` motor e APIs auxiliares em Python

## Documentos

- `docs/environment.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/mt5-runtime.md`
- `docs/http-contract.md`
- `docs/demo-test-playbook.md`

## Estado do repositorio

Repositorio com documentacao inicial, runtime Docker do MT5, scripts de bootstrap local e esqueleto executavel da integracao `MT5 -> Python service`.
