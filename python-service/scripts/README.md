# Scripts do serviço

Os comandos permanecem neste diretório para preservar os runbooks existentes. Novos scripts devem
seguir um dos prefixos abaixo até a migração para subcomandos da CLI `lotus`.

| Prefixo | Uso |
|---|---|
| `cache_` | publicar ou atualizar snapshots consumidos pelo portal |
| `build_` | produzir um artefato reproduzível a partir de dados congelados |
| `research_` | explorar hipóteses sem promoção operacional |
| `validate_` | aplicar gates congelados a um resultado existente |
| `report_` | gerar relatórios sem alterar a hipótese |
| `inspect_` | diagnóstico somente leitura |
| `download_` / `import_` / `upload_` | mover dados entre fronteiras explícitas |

Todo script novo deve:

- possuir descrição no módulo e `--help`;
- aceitar paths e período por argumento;
- registrar dataset, parâmetros e custos no output;
- falhar sem sobrescrever artefatos incompatíveis;
- reutilizar módulos de `app/` em vez de duplicar regras de estratégia;
- ter ao menos um teste para parsing, seleção ou contrato de saída.

Scripts históricos sem prefixo compatível devem ser renomeados apenas junto da atualização de todos
os runbooks e workflows que os referenciam.
