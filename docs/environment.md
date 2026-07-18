# Avaliacao do ambiente

Data da avaliacao: 2026-07-17.

## Disponivel nesta maquina

- Linux Ubuntu x86_64
- Python 3.12.3
- pip 24.0
- Node.js 22.22.3
- npm 12.0.0
- pnpm 11.8.0
- Docker 29.5.3
- Git 2.43.0
- `Xvfb` e `xvfb-run`

## Nao disponivel hoje

- `wine`
- MetaTrader 5 instalado
- ambiente Windows dentro do Wine
- pacote `MetaTrader5` instalavel no Python Linux desta maquina

## Restricoes reais para MT5 neste servidor

### 1. MT5 em Linux depende de Wine

O fornecedor do MT5 documenta execucao em Linux via Wine. Sem isso, nao existe terminal MT5 operacional neste host.

### 2. Integracao Python direta com MT5 nao esta pronta neste host Linux

O pacote oficial `MetaTrader5` nao apareceu como distribuicao instalavel neste Python Linux atual. Isso indica que nao devemos assumir uma stack "Python Linux -> MT5" direta como caminho principal de producao.

### 3. O servidor e headless

Existe `Xvfb`, o que ajuda a rodar UI Windows/Wine sem display fisico. Isso reduz atrito operacional, mas nao substitui a instalacao de Wine nem do terminal MT5.

## O que e necessario para um bot MT5 viavel aqui

### Camada de execucao

- instalar `wine64`
- instalar MT5 via script oficial Linux
- validar inicializacao do terminal em sessao headless
- conectar uma conta demo primeiro
- confirmar logs, reconexao e persistencia de sessao

### Camada de estrategia

- implementar servico Python separado
- expor endpoint local para decisao de trade
- registrar sinais, contexto, resposta e latencia

### Camada de risco

- limite por operacao
- limite diario de perda
- limite de trades por janela
- bloqueio por horario
- bloqueio por spread/volatilidade
- kill switch manual

### Camada de observabilidade

- logs estruturados
- diario de sinais
- diario de ordens
- auditoria de posicoes
- alertas de falha de conexao MT5

## Conclusao

Este ambiente suporta o projeto, mas nao suporta ainda a execucao MT5 pronta para uso.

Antes de desenvolver o bot propriamente dito, precisamos preparar o runtime do MT5 ou assumir arquitetura hibrida:

- MT5/MQL5 para execucao
- Python Linux para estrategia e operacao

## Decisao do passo 1

Como o host nao oferece `sudo` sem senha, o caminho adotado neste projeto e:

- preparar `Wine + Xvfb` em container Docker
- manter o host limpo
- deixar o runtime reproduzivel dentro do repositorio
