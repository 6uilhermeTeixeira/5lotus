# MT5 Daytrade Bot

Projeto novo para desenvolver um bot de daytrade com execucao na plataforma MetaTrader 5.

Status atual: fase de planejamento e avaliacao do ambiente.

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

## Estrutura inicial

- `docs/` documentacao do projeto
- `mt5/` artefatos da camada MT5/MQL5
- `python-service/` motor e APIs auxiliares em Python

## Documentos

- `docs/environment.md`
- `docs/architecture.md`
- `docs/roadmap.md`

## Estado do repositorio

Repositorio inicial criado apenas com documentacao e plano tecnico.
