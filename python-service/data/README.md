# Dados do serviço

| Diretório | Conteúdo |
|---|---|
| `backtests/` | snapshots normalizados usados em comparações de risco equivalente |
| `backtests-operational/` | snapshots com risco e custos do cenário operacional |
| `research/` | artefatos exploratórios e evidências não promovidas |
| `bots.json` | nomes e descrições públicas do catálogo ativo |
| `legacy-bots.json` | catálogo preservado apenas para auditoria |

Snapshots seguem `<bot-id>-<periodo-dias>.json`. O perfil, profundidade histórica e disponibilidade
do replay não são declarados aqui; pertencem a `app/strategies/registry.py`.

Resultados de pesquisa não autorizam promoção. Cada conjunto deve informar, no nome ou manifesto,
o dataset, cobertura, custos, parâmetros e status. Datasets brutos e arquivos grandes regeneráveis
devem ser publicados fora do Git; o repositório deve manter apenas manifestos e relatórios compactos.
