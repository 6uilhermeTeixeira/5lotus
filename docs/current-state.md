# Estado técnico atual — 2Lotus

Atualizado em 2026-09-10 e validado contra o commit `9ea3997`.

## Estado atual dos serviços

| Serviço | Estado atual | Conta atual | Estado-alvo |
| --- | --- | --- | --- |
| `2lotus` | hospeda laboratório e, provisoriamente, o Live Core | demo já registrada | operar somente laboratório/forward demo |
| `live-core` | ocioso | nenhuma conta operacional | hospedar o Live Core e receber a conta real |

A separação já existe nos repositórios, mas ainda não foi concluída no runtime. Assim, “Live Core”
pode designar hoje o código/fluxo executado dentro do serviço `2lotus`; não significa que o serviço
dedicado `live-core` esteja ativo nem que exista conta real conectada.

## Missão

O 2Lotus é o laboratório privado de pesquisa e validação de estratégias XAUUSD/M5. Ele coleta ou
lê dados de mercado, executa replay causal, avalia estratégias em shadow, registra telemetria e
publica um portal autenticado. Não está autorizado a enviar ordens reais.

## Componentes

- Serviço FastAPI/Python 3.12: portal, decisão shadow, ingestão, paper tracking e replay.
- Supabase: histórico, ticks, sinais, paper/tick-shadow trades, resultados, snapshots, runtime status
  e respostas idempotentes.
- MT5: `SyncLeadBridgeEA`, coletor forward de ticks e exportador histórico.
- Pipeline: download Dukascopy resumível, manifesto SQLite, BI5, agregação e releases Parquet.
- Pesquisa: scripts e artefatos para reconstrução, seletores, robustez, custos e holdouts.
- Deploy: Vercel para o serviço web e Docker Compose para API/MT5/noVNC local.

## Catálogo atual

O catálogo JSON ativo possui 21 perfis distribuídos nas famílias Scalp, Sell, Buy e Combined.
O inventário estrutural é validado por `app/strategies/registry.py`, enquanto `data/bots.json`
mantém os nomes e textos públicos. Todos permanecem em shadow. O combinado pode retornar
`parallel_candidates`; o EA atual aceita uma decisão executável por consulta e não deve usá-lo
como executor real.

## Dados e replay

O histórico é identificado por mercado, não por bot. Replays web leem snapshots; geração e pesquisa
ocorrem fora da requisição. Releases Parquet ficam fora do Git em `/home/codexops/lotus-data` e devem
ser verificadas por hash. Ticks forward e backfills históricos são mantidos separados.

O pipeline publicador ainda pertence a este repositório. Referências que atribuem essa função ao
`1lotus` ou que enviam bundles ao antigo `3lotus` são legadas.

## Segurança

Portal e APIs de leitura usam cookie assinado; ingestão e decisão usam chave própria. `/health` é
liveness, `/ready` valida configuração/Supabase e `/api/metrics` exige sessão. RLS impede acesso de
`anon`/`authenticated`; o backend usa service role. Live permanece desativado e os perfis retornam hold.

O serviço `2lotus` deve continuar associado apenas à conta demo. A migração da conta real pertence
ao serviço dedicado e não deve reutilizar secrets, store, URLs de ingestão ou identificação da demo.

## Qualidade conhecida

Em 2026-09-10, 123 testes do serviço e nove testes do pipeline passaram; Ruff passou. A cobertura
do serviço foi 65%, com lacunas em `main.py` (34%), `backtest.py` (39%), autenticação e sincronização
de histórico. Há aviso de depreciação Starlette/httpx nos testes.

## Documentos legados

`2lotus-operational-setup.md` e partes de `tick-research.md` preservam IDs `bot-*` e etapas históricas
úteis para auditoria, mas não devem ser usados isoladamente para configurar o runtime atual. O
catálogo JSON, `.env.example`, migrations recentes e EAs são as fontes de verdade executáveis.
