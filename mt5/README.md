# Camada MT5

Esta pasta vai conter:

- Expert Advisors em MQL5
- scripts auxiliares do terminal
- documentacao de deploy no MT5

## Implementacao atual

Foi criado um EA inicial em:

- `experts/SyncLeadBridgeEA.mq5`

## Papel do EA

- coletar contexto basico do simbolo
- coletar historico recente de candles
- chamar o servico Python em `POST /decision`
- registrar a resposta no log do terminal
- executar a ordem automaticamente quando:
  - o servico retornar `buy` ou `sell`
  - `EnableOrderExecution=true`

Nesta fase, o caminho de execucao ja existe, mas ainda nao foi validado dentro do terminal MT5 neste servidor porque o ambiente Wine continua em estabilizacao.

## Teste em demo

O passo a passo operacional do teste fim a fim esta em:

- `../docs/demo-test-playbook.md`
