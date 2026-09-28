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

## Próxima etapa: forward test shadow e consolidação da plataforma

- acumular amostra independente dos seis bots
- acompanhar heartbeat, latência, gaps e paper trades diariamente
- confirmar custos reais, timezone e sequência intrabar com ticks
- definir critérios formais de promoção/rejeição por estratégia
- testar recuperação após queda do MT5, API e rede
- consolidar métricas por instância e alertas operacionais
- separar formalmente pipeline, laboratório, Live Core e site institucional
- substituir IDs históricos `bot-*` nos runbooks pelos IDs `core-*` efetivamente catalogados
- retirar o Live Core do serviço `2lotus` sem interromper a conta demo registrada
- ativar o serviço `live-core` isolado e conectar nele a conta real somente após preflight

O detalhamento, critérios de aceite e prioridades estão em [`PRD-improvements.md`](PRD-improvements.md).

## Fora do escopo atual

- ativação em conta real
- aumento automático de risco
- garantia de retorno baseada no replay
