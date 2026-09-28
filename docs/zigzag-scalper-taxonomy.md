# Taxonomia do ZigZag Scalper

Esta é a referência de organização da família ZigZag Scalper. Ela separa a
origem de um sinal das camadas que selecionam, bloqueiam, roteiam ou compõem
esses sinais. Nomes públicos seguem esta taxonomia; IDs técnicos, perfis e
snapshots de replay permanecem estáveis para preservar auditoria.

## V1 — Gatilhos

| Versão | Estratégia | Papel |
|---|---|---|
| V1.0 | `core-zigzag` | Rompimento estrutural M30; referência de melhor desempenho histórico. |
| V1.1.0 | `core-zigzag-v12` | Microreteste causal por ticks após o rompimento. |
| V1.2.0 | `core-zigzag-v13` | Fechamento completo M30 além do pivô, com entrada no primeiro M5 seguinte. |
| V1.3.0 | `core-zigzag-v2` | Gatilho estrutural com impulso de ticks e execução própria. |

## V2 — Roteadores de Gatilho

| Versão | Estratégia | Papel |
|---|---|---|
| V2.0 | `core-zigzag-v3` | Escolhe V1.0 ou V1.3.0 pelo range médio causal de M5. |
| V2.1 | `core-zigzag-v5` | Roteia V1.0/V1.3.0 por regime e pode acionar o filtro temporal de transição V5.0. |

## V3 — Filtros Contextuais

| Versão | Estratégia | Papel |
|---|---|---|
| V3.0 | `core-zigzag-v6` | Filtra vendas da V2.1 por sessão, regime e EMA50. |
| V3.1 | `core-zigzag-v7` | Filtra vendas da V2.1 por contexto H1, EMA50 e estocástico tardio. |
| V3.2 | `core-zigzag-v9` | Filtra compras da V2.1 por direção H1 e distância causal acima da EMA50 em ATR. |

## V4 — Roteadores de Contexto

| Versão | Estratégia | Papel |
|---|---|---|
| V4.0 | `core-zigzag-v10` | Roteia compras para V3.2 e vendas para V3.1 sem avaliar o ramo alternativo. |

## V5 — Filtros Temporais

| Versão | Estratégia | Papel |
|---|---|---|
| V5.0 | `core-zigzag-v4` | Bloqueia V1.0 por dia, horário UTC e direção. |
| V5.1 | `core-zigzag-v8` | Calendário mensal de assertividade aplicado ao ramo temporal composto. |

## V6 — Roteadores Temporais

| Versão | Estratégia | Papel |
|---|---|---|
| V6.0 | `core-zigzag-v72` | Escolhe V2.0 na quarta/quinta UTC e V3.1 nos demais dias. |

## Categorias futuras

## V7 — Orquestração Final

| Versão | Estratégia | Papel |
|---|---|---|
| V7.0 | `core-zigzag-v11` | Aplica os filtros temporais à V4.0 e entrega uma única decisão final, sem reavaliar gatilhos alternativos. |

A V7.0 permanece em shadow e combina os ramos ZigZag sob prioridade, exposição e
risco compartilhados. O atual portfólio combinado multi-família não é uma V7 ZigZag.

## Regras de evolução

1. Um novo mecanismo de entrada pertence à V1.
2. Uma regra que escolhe um gatilho pertence à V2.
3. Uma regra que apenas aprova ou bloqueia por condições de mercado pertence à V3.
4. Uma regra que escolhe ramos por contexto pertence à V4.
5. Uma regra que apenas aprova ou bloqueia por calendário pertence à V5.
6. Uma regra que escolhe ramos pelo tempo pertence à V6.
7. V7 só recebe perfis quando sua responsabilidade própria existir.

Não renumerar IDs, perfis ou arquivos de replay para refletir a taxonomia. A
versão pública descreve a função arquitetural; o identificador técnico garante
continuidade de dados e reprodutibilidade.
