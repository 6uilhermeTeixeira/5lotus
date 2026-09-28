# PRD — evolução da plataforma 2Lotus

## Objetivo

Transformar o laboratório em uma plataforma de pesquisa reproduzível, com fronteiras claras,
evidência fora da amostra e promoção segura para o Live Core.

## P0 — reconciliar operação e documentação

- Gerar runbooks a partir do catálogo `core-*` e dos inputs reais do EA.
- Marcar blocos históricos `bot-*` como legado ou migrá-los com tabela explícita de equivalência.
- Validar links, paths, variáveis e IDs citados em Markdown no CI.

Aceite: um operador novo consegue subir shadow usando somente a documentação atual; CI falha quando
um ID, script ou variável documentada deixa de existir.

## P0 — separar demo e conta real

- Congelar o serviço `2lotus` como ambiente demo com a conta já registrada.
- Provisionar o serviço `live-core` com URLs, secrets, persistência, logs e alertas independentes.
- Remover a execução provisória do Live Core no `2lotus` somente após validar o novo serviço.
- Impedir que a conta real seja aceita no `2lotus` e que a demo seja confundida com a allowlist real.

Aceite: o inventário mostra uma conta por serviço; a demo continua funcional durante a migração; o
novo Live Core inicia desarmado, falha fechado e passa health/readiness antes de receber a conta real.

## P0 — contrato de promoção

- Formalizar bundle versionado com estratégia, commit, dataset/hash, parâmetros, custos, holdouts,
  limitações, aprovação e rollback.
- Testar publicação/importação contra o `2lotus-live-core`, não o antigo path `3lotus/python-service`.
- Proibir promoção sem forward test mínimo e critérios previamente congelados.

## P1 — dados e reprodutibilidade

- Extrair o pipeline para fronteira/repositório próprio ou declarar formalmente sua propriedade aqui.
- Registrar origem, timezone, cobertura, gaps e hashes em cada replay.
- Automatizar retenção: ticks fechados em Parquet e janela operacional no banco.

## P1 — qualidade e arquitetura

- Elevar cobertura a 80%, priorizando rotas, replay, autenticação e history sync.
- Dividir `main.py` em routers e continuar a extração de `strategy.py` por família.
- Resolver a depreciação Starlette/httpx e testar builds Vercel/Docker no CI.
- Criar testes de contrato MQL5/API para `parallel_candidates`, idempotência e stale data.

## P1 — forward test e observabilidade

- Painel de coorte por versão de estratégia, dataset e broker.
- Alertas para gaps, heartbeat, latência, spread e divergência replay/forward.
- Critérios congelados de promoção/rejeição antes da próxima amostra.

## P2 — governança da pesquisa

- Registro de hipóteses com status proposta, em teste, rejeitada ou candidata.
- Separar artefatos operacionais de grandes datasets e resultados regeneráveis.
- Relatórios compactos com in-sample, holdout, custos e sensibilidade lado a lado.
