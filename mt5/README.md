# Camada MT5

Esta pasta vai conter:

- Expert Advisors em MQL5
- scripts auxiliares do terminal
- documentacao de deploy no MT5

## Implementacao atual

Foi criado um EA inicial em:

- `experts/SyncLeadBridgeEA.mq5`
- `experts/TickCollectorEA.mq5`, coletor isolado e sem funções de negociação
- `scripts/TickHistoryExporter.mq5`, exportador sob demanda do histórico de ticks da corretora

O `SyncLeadBridgeEA` também possui um exportador histórico Fusion/MT5 opcional. Quando
`EnableFusionHistoryExport=true`, ele retoma uma janela de até 365 dias em blocos de uma hora,
persistindo o checkpoint em `Common/Files/2lotus-ticks/<collector>/history-state.txt`. O exportador
somente lê `CopyTicksRange` e escreve arquivos; ele não envia, modifica ou encerra ordens.

## Papel do EA

- coletar contexto basico do simbolo
- coletar historico recente de candles
- manter uma janela circular de 905 segundos de mids Bid/Ask e derivar impulso de 5, 10, 30, 60 e 900 segundos
- chamar o servico Python em `POST /decision`
- registrar a resposta no log do terminal
- executar a ordem automaticamente quando:
  - o servico retornar `buy` ou `sell`
  - `EnableOrderExecution=true`

Nesta fase, o caminho de execucao ja existe, mas ainda nao foi validado dentro do terminal MT5 neste servidor porque o ambiente Wine continua em estabilizacao.

A configuração do coletor de ticks e do uploader está em `../docs/tick-research.md`.
Os ticks ingeridos também avançam o lifecycle shadow do Bot 19; esse caminho não contém chamadas
de negociação e nunca depende de `EnableOrderExecution`.

## Teste em demo

O passo a passo operacional do teste fim a fim esta em:

- `../docs/demo-test-playbook.md`
