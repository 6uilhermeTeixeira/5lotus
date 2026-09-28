# Registro de estratégias

O arquivo `python-service/app/strategies/registry.py` é a fonte de verdade estrutural dos perfis ativos.
Ele centraliza os dados que o roteador, o replay e o portal precisam conhecer sem importar a lógica de
execução de cada estratégia.

## Responsabilidades

Cada `StrategyDefinition` declara:

- `bot_id` e `profile`;
- família pública (`scalp`, `sell`, `buy` ou `combined`);
- módulo de roteamento (`core`, `tick` ou `portfolio`);
- posição da variante no portal;
- quantidade mínima de candles no replay;
- quantidade de candles recarregada no fluxo de decisão;
- política de regime;
- canais de contexto causal injetados pelo replay;
- política de sessão histórica;
- participação na tela operacional;
- disponibilidade do replay OHLCV.

O catálogo `data/bots.json` continua sendo a fonte dos nomes e textos exibidos. Um teste de contrato
exige correspondência exata entre cada bot ativo do catálogo e uma definição do registro.
Para a linhagem e a ordem pública da família ZigZag Scalper, consulte
[`zigzag-scalper-taxonomy.md`](zigzag-scalper-taxonomy.md).

## Inclusão de uma estratégia

1. Implemente o setup e o avaliador no módulo da família.
2. Acrescente o handler ao roteador da família.
3. Registre uma única `StrategyDefinition`.
4. Acrescente o conteúdo público ao `data/bots.json`.
5. Gere os snapshots de replay aplicáveis.
6. Adicione testes do sinal e execute `test_strategy_registry.py`.

Não crie novas listas de perfis em `pages.py`, `main.py` ou `backtest.py`. Metadados compartilhados
devem entrar no registro. Exceções temporárias para pesquisas legadas precisam ser explicitamente
marcadas e removidas quando o perfil for promovido ao catálogo ativo.

## Invariantes

- `bot_id` e `profile` são únicos.
- Todo item ativo do catálogo está registrado.
- Perfis sem replay causal compatível declaram `replay_supported=False`.
- Uma estratégia experimental permanece bloqueada no próprio avaliador; o campo `operational` apenas
  controla sua visibilidade e não concede autorização de execução.
