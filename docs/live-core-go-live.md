# Live Core — preparação para MT5

## Estado atual

O Wine não precisa ser instalado no host. O serviço `mt5` de `compose.yaml` constrói uma imagem
Ubuntu com Wine, Xvfb e noVNC, e persiste o terminal em `.runtime/mt5-prefix`.

O catálogo ativo contém somente ZigZag V3, Stochastic V3, Multitemporal V3 e Combinação V3. Esses
perfis continuam com trava de execução `shadow`. Esta trava é deliberada: conectar uma conta não
deve, sozinho, liberar ordens.

## Escolha obrigatória de execução

As três V3 individuais e a Combinação V3 são quatro visões no painel, mas não devem operar juntas.
A combinação reproduz os sinais das três estratégias e executá-la junto com as individuais duplicaria
risco. Antes do teste em demo, escolha exatamente um modo:

1. uma única V3 individual; ou
2. a Combinação V3, depois da implementação e validação do executor de múltiplas posições.

O EA deixa `ExecutionBotId` vazio por padrão. Ele consulta as quatro estratégias para telemetria, mas
não envia ordens.

## Sequência recomendada

1. Copie `.env.example` para `.env` e preencha somente no servidor. Nunca envie as credenciais pelo chat.
2. Execute `./scripts/preflight-live-core.sh`.
3. Construa o runtime com `./scripts/build-mt5-runtime.sh`.
4. Inicie com `./scripts/run-mt5-desktop.sh`.
5. Abra `http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080` no próprio servidor ou por túnel SSH.
6. Instale/inicie o MT5 e conecte primeiro uma conta demo da Fusion Markets.
7. Execute `./scripts/install-mt5-expert.sh`, compile o EA no MetaEditor e confirme zero erros.
8. Na allowlist de WebRequest do MT5, adicione `http://127.0.0.1:1112`.
9. Anexe o EA a um gráfico XAUUSD M5 com `EnableOrderExecution=false` e `ExecutionBotId` vazio.
10. Observe pelo menos uma sessão completa, incluindo heartbeat, candles, candidatos e ausência de duplicatas.

## Bloqueios antes de dinheiro real

- validar em demo o símbolo exato da Fusion (`XAUUSD` pode ter prefixo/sufixo);
- confirmar `_Point`, `tick size`, `tick value`, lote mínimo e step diretamente no terminal;
- medir spread real, slippage, comissão e swaps da conta;
- validar SL/TP contra `SYMBOL_TRADE_STOPS_LEVEL` e `SYMBOL_TRADE_FREEZE_LEVEL`;
- reconciliar tickets, deals parciais, comissão e PnL após reinício;
- implementar o executor das `parallel_candidates` antes de promover a Combinação V3;
- definir limite monetário diário, perda máxima, exposição total e kill switch independentes da estratégia;
- promover explicitamente apenas o bot escolhido, mantendo os demais em shadow.

## Dados da conta

Os campos `DAYTRADE_MT5_LOGIN`, `DAYTRADE_MT5_PASSWORD` e `DAYTRADE_MT5_SERVER` são inventário de
configuração, mas o runtime ainda não faz login automático com eles. O primeiro login é manual via
noVNC e fica persistido no Wine prefix. Não coloque senha em argumentos de processo ou logs.

## Critério mínimo de prontidão

O sistema só está pronto para promoção quando o preflight não apresenta `FAIL`, o terminal está
conectado, o EA está compilado, `/health` responde, as quatro estratégias têm heartbeat e uma sessão
demo completa fecha e reporta negócios corretamente. A promoção live é uma mudança separada.
