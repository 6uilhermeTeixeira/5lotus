# Roadmap inicial

## Fase 0 - Preparacao do ambiente

- [ ] instalar Wine
- [ ] instalar MT5 no Linux
- [ ] validar execucao headless
- [ ] conectar conta demo
- [ ] documentar paths, logs e recuperacao

## Fase 1 - Base do projeto

- [ ] definir estrategia inicial
- [ ] definir simbolos e timeframes
- [ ] definir regras de entrada e saida
- [ ] definir limites de risco
- [ ] definir horario operacional

## Fase 2 - Arquitetura executavel

- [ ] criar EA MQL5 minimo
- [ ] criar Python service minimo
- [ ] criar contrato HTTP entre EA e Python
- [ ] registrar logs estruturados

## Fase 3 - Simulacao e validacao

- [ ] backtest historico
- [ ] replay controlado
- [ ] paper trading em demo
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
