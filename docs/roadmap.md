# Roadmap

## Concluído

- runtime MT5 reproduzível em Docker
- serviço Python e contrato HTTP
- histórico canônico desacoplado de estratégias
- seis estratégias selecionadas em shadow
- replay causal anual e snapshots versionados
- portal autenticado, comparação e simulador por faixas
- painel de saúde operacional
- backup e remoção das estratégias rejeitadas

## Próxima etapa: forward test shadow

- acumular amostra independente dos seis bots
- acompanhar heartbeat, latência, gaps e paper trades diariamente
- confirmar custos reais, timezone e sequência intrabar com ticks
- definir critérios formais de promoção/rejeição por estratégia
- testar recuperação após queda do MT5, API e rede

## Fora do escopo atual

- ativação em conta real
- aumento automático de risco
- garantia de retorno baseada no replay
