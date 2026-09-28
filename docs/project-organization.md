# Organização do projeto

## Fronteiras

| Área | Responsabilidade | Não deve conter |
|---|---|---|
| `python-service/app` | API, regras, replay e persistência | datasets brutos e experimentos descartáveis |
| `python-service/app/services` | políticas reutilizáveis sem dependência de FastAPI | rotas, autenticação e estado HTTP |
| `python-service/app/strategies` | registro e roteamento por família | HTML, acesso direto ao Supabase ou scripts operacionais |
| `python-service/tests` | contratos e regressões do serviço | resultados históricos usados como fonte de verdade |
| `python-service/scripts` | comandos operacionais e pesquisas reproduzíveis | lógica exclusiva que não exista em módulos testáveis |
| `python-service/data/backtests` | snapshots normalizados compactos | downloads brutos |
| `python-service/data/backtests-operational` | snapshots com risco e custos operacionais | resultados editados manualmente |
| `python-service/data/research` | evidências exploratórias com manifesto | credenciais e estado do runtime |
| `market-data-pipeline` | aquisição e publicação de datasets | decisão ou execução de estratégias |
| `mt5` e `infra/mt5-runtime` | ponte e runtime MetaTrader | regras de seleção de estratégia |
| `supabase/migrations` | evolução imutável do banco | dados de pesquisa |

## Convenções

- Perfis ativos são declarados em `app/strategies/registry.py`.
- Nomes públicos permanecem em `data/bots.json`.
- Uma estratégia pertence a exatamente uma família: Scalp, Sell, Buy ou Combined.
- A família ZigZag Scalper segue a taxonomia de gatilhos, roteadores e filtros em
  `docs/zigzag-scalper-taxonomy.md`; a ordem pública não altera IDs técnicos.
- Resultados regeneráveis carregam período no nome: `<bot-id>-<dias>.json`.
- Scripts de pesquisa devem documentar dataset, parâmetros, custos e output.
- Regras compartilhadas entram em módulos do serviço; scripts apenas orquestram essas regras.
- Nenhum módulo web mantém listas próprias de perfis ativos.
- Serviços recebem armazenamento e datasets como dependências; `main.py` mantém wrappers compatíveis enquanto as rotas são migradas.

## Extrações concluídas

- Registro tipado e roteamento das estratégias ativas por família.
- Construção das séries de comparação em `app/services/comparison.py`.
- Políticas de cache, recorte, normalização e candles de replay em `app/services/replays.py`.
- Construção dos estados de operações e conta em `app/services/runtime.py`.
- Rotas HTML autenticadas do portal em `app/routers/portal.py`.
- APIs de comparação, gráfico histórico e replay em `app/routers/replays.py`.
- APIs autenticadas de ingestão de trades, candles e ticks em `app/routers/ingestion.py`.
- Saúde, conta, operações, métricas e configuração em `app/routers/operational.py`.
- Decisão MT5 e persistência associada em `app/routers/decision.py`.
- Contexto por decisão e piso mínimo de shadow em `app/services/decision_context.py`.

## Próximas extrações

1. Mover gradualmente os setups de `app/strategy.py` para `app/strategies/<familia>/`.
2. Extrair gradualmente a lógica interna do handler de decisão para serviços testáveis; todos os grupos de rotas já estão registrados em módulos próprios.
3. Separar `SupabaseStore` por domínio de persistência.
4. Migrar HTML, CSS e JavaScript de `pages.py` para templates e assets estáticos.
5. Publicar artefatos grandes fora do Git, mantendo manifestos compactos no repositório.

Cada etapa deve ser pequena, preservar os contratos HTTP e passar a suíte antes da próxima extração.
