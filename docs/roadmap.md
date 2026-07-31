# Roadmap inicial

## Fase 0 - Preparacao do ambiente

- [x] instalar Wine
- [x] instalar MT5 no Linux
- [x] validar execucao headless
- [x] conectar conta demo
- [x] documentar paths, logs e recuperacao

## Fase 1 - Base do projeto

- [x] definir estrategia inicial
- [x] definir simbolos e timeframes
- [x] definir regras de entrada e saida
- [x] definir limites de risco
- [ ] definir horario operacional

## Fase 2 - Arquitetura executavel

- [x] criar EA MQL5 minimo
- [x] criar Python service minimo
- [x] criar contrato HTTP entre EA e Python
- [x] registrar logs estruturados

## Fase 3 - Simulacao e validacao

- [ ] backtest historico
- [x] replay controlado
- [x] paper trading em demo
- [x] cinco estratégias independentes em shadow no mesmo runtime
- [x] comparação consolidada no portal
- [ ] validacao de risco e falhas

## Fase 4 - Operacao assistida

- [ ] dashboard minimo de saude
- [ ] alertas operacionais
- [ ] bloqueios de emergencia
- [ ] checklist pre-market e post-market

## Perguntas que precisamos fechar antes da implementacao

1. O bot vai operar qual mercado?
2. Qual broker e servidor MT5 serao usados?
3. O bot sera scalping, momentum, mean reversion ou breakout?
4. Qual timeframe principal?
5. Qual limite diario de perda?
6. Vai operar so em conta demo no primeiro ciclo?
