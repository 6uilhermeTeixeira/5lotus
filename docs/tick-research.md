# Coleta de ticks para pesquisa

## Objetivo

Registrar Bid/Ask do broker com precisão de milissegundos para reconstruir, em shadow, estratégias
com duração de segundos. O coletor não contém funções de negociação e não altera o
`SyncLeadBridgeEA`.

O histórico Happy Gold do Myfxbook deve ser tratado como forward test. Os horários foram publicados
sem timezone. A localização do vendedor na Alemanha torna `Europe/Berlin` uma hipótese de pesquisa,
mas não comprova o timezone da conta ou do servidor.

## Fluxo

```text
TickCollectorEA.mq5
  -> Common/Files/2lotus-ticks/<collector>/*.ready.csv
tick-uploader
  -> POST /api/ticks em lotes de até 1000
FastAPI
  -> validação, autenticação e rate limit
Supabase
  -> market_ticks, deduplicado por collector/symbol/time_msc/sequence
```

O EA não chama `WebRequest`. Chamadas HTTP síncronas bloqueariam sua fila de eventos e poderiam
reduzir a fidelidade da captura. Arquivos `.part.csv` ainda estão sendo escritos; somente arquivos
`.ready.csv` são consumidos. Um arquivo só é removido depois que todos os lotes retornam HTTP 204.

## Ativação

1. Aplicar a migration `20260808190000_add_market_tick_research.sql`.
2. Recriar as imagens com `docker compose build api`.
3. Iniciar o runtime com `docker compose up -d mt5 api tick-uploader`.
4. Compilar `mt5/experts/TickCollectorEA.mq5` no MetaEditor.
5. Abrir o gráfico XAUUSD e anexar o coletor com `CaptureSymbol=XAUUSD`.
6. Usar um `CollectorId` estável que identifique ambiente e broker, sem credenciais.

O coletor recusa inicialização quando o símbolo do gráfico é diferente de `CaptureSymbol`.

## Recuperação histórica

Execute `mt5/scripts/TickHistoryExporter.mq5` uma vez no terminal conectado. Por padrão, ele solicita
30 dias de `XAUUSD` em blocos de uma hora e grava os mesmos arquivos `.ready.csv` usados pelo
uploader. O arquivo `history-export-summary.txt` informa quantos blocos tinham dados, estavam vazios
ou falharam.

`CopyTicksRange` retorna apenas o histórico mantido pelo servidor da corretora atual. Portanto, a
ausência de ticks antigos não prova que o mercado estava fechado e não pode ser corrigida pelo
MetaTrader sem outra fonte de dados. Para ampliar a janela, altere `LookbackDays`; mantenha
`ChunkMinutes` entre 15 e 60 para limitar memória e permitir diagnosticar lacunas.

## Verificação

```sql
select
  collector_id,
  symbol,
  min(timestamp_utc) as first_tick,
  max(timestamp_utc) as last_tick,
  count(*) as ticks
from public.market_ticks
group by collector_id, symbol;
```

Verifique gaps por `time_msc`, mudanças de spread e quantidade de ticks por minuto antes de usar o
dataset. Ausência de ticks não significa ausência de movimento: pode indicar mercado fechado,
desconexão ou falha do terminal.

## Retenção

Ticks crescem muito mais rápido que candles. A tabela deve ser monitorada diariamente durante a
primeira semana. Depois de validar a coleta, exporte períodos fechados para Parquet comprimido e
defina retenção no banco sem apagar a cópia de pesquisa.

Depth of Market não faz parte desta primeira coleta. Em XAUUSD OTC ele depende do broker, não possui
equivalência garantida com a origem do forward test e normalmente não oferece histórico reproduzível.

## Fonte histórica complementar: Dukascopy

Para o período anterior ao histórico disponível no MT5, use `scripts/download_dukascopy_ticks.py`.
Ele baixa `XAUUSD` tick a tick em UTC, preservando Bid e Ask em arquivos diários e retomando arquivos
já validados. A fonte é complementar: preços e spreads da Dukascopy não são necessariamente iguais
aos da corretora desconhecida usada no forward test.

```bash
python-service/.venv/bin/python python-service/scripts/download_dukascopy_ticks.py \
  --output .runtime/market-data/dukascopy/happy-gold-2025-2026 \
  --cache .runtime/market-data/dukascopy/cache
```

## Histórico de referência do Myfxbook

As 773 operações publicadas foram normalizadas em
`python-service/data/research/happy_gold_forward_trades.csv`. Os campos `open_time_local` e
`close_time_local` preservam o horário exibido pelo Myfxbook. Após a correlação de preços e a
confirmação pela mudança de horário de verão, `source_timezone=Europe/Helsinki` registra o horário
EET/EEST do servidor. O arquivo `.validation.json` registra hashes e totais conferidos contra a
página pública.

O importador reproduzível está em `python-service/scripts/import_myfxbook_history.py` e interrompe a
geração se contagem, lados, lotes, lucro ou número de operações não perdedoras divergirem dos totais
publicados.

### Inferência preliminar de timezone

O correlacionador `python-service/scripts/correlate_myfxbook_ticks.py` compara Ask para compras e Bid
para vendas dentro de cada minuto publicado. Nos 81 trades entre 15 de outubro e 4 de novembro com
ticks Dukascopy completos, `Europe/Helsinki` apresentou erro mediano de preço de `0.005`, contra
`7.302` para `Europe/Berlin` e `15.145` para UTC.

A mudança de horário de verão reforça a inferência: UTC+3 corresponde antes de 26 de outubro de 2025
e UTC+2 corresponde depois dessa data. Assim, o horário publicado deve ser tratado provisoriamente
como EET/EEST (`Europe/Helsinki`), típico de servidor de corretora, e não como o timezone alemão do
vendedor. O CSV estruturado usa `source_timezone=Europe/Helsinki`; a evidência derivada está em
`happy_gold_tick_timezone_matches.csv` e `happy_gold_tick_timezone_summary.json`.

### Reconstrução de segundos

`python-service/scripts/reconstruct_myfxbook_trade_times.py` usa o melhor preço de entrada dentro do
minuto, tolerância de `0.005` para empates, lado correto do spread e duração com tolerância de 1,5
segundo. Nos 81 trades com ticks disponíveis, todas as entradas receberam timestamp candidato; 70
também receberam saída candidata. O resultado separa `high`, `medium`, `low` e `entry_only`.

Essa reconstrução não transforma candidatos em fills comprovados. Em movimentos rápidos, a sequência
de preços da Dukascopy pode divergir por segundos da corretora desconhecida. Casos `low` e
`entry_only` não devem ser usados para inferir regras de saída; somente `high` e, com análise de
sensibilidade, `medium` entram na amostra principal.

### Microestrutura de entrada e controles

`python-service/scripts/extract_happy_gold_entry_features.py` extrai janelas de 1, 3, 5, 10, 30 e
60 segundos antes das 30 entradas `high` ou `medium`. O movimento é medido na direção da operação:
positivo para alta antes de Buy e para queda antes de Sell. A mediana chegou a 88,25 pips em 10
segundos e 174,35 pips em 30 segundos; 90% e 93,3% das entradas, respectivamente, já se moviam na
direção da ordem.

Entradas isoladas não demonstram poder de seleção. Por isso,
`python-service/scripts/compare_happy_gold_entry_controls.py` cria até cinco controles pareados por
operação, no mesmo dia e com a mesma direção hipotética, afastados entre 19 e 55 minutos e fora de
uma zona de três minutos de qualquer entrada publicada. A amostra atual contém 30 entradas e 146
controles.

O movimento direcional de 30 segundos foi o atributo individual mais estável: mediana de 174,35
pips nas entradas contra -6,25 nos controles, AUC 0,859 e limiar exploratório de 95,5 pips. Ao
recalibrar o limiar deixando um dia inteiro fora por vez, a sensibilidade foi 80,0%, a especificidade
82,2% e a acurácia balanceada 81,1%. O limiar ainda é in-sample, os controles do mesmo dia são
correlacionados e o trecho disponível cobre apenas 14 dias; ele deve alimentar uma estratégia shadow,
não uma regra de produção. Os dados derivados ficam em `happy_gold_entry_features.csv`,
`happy_gold_entry_controls.csv` e nos respectivos arquivos `.summary.json`.

### Estratégia shadow de impulso

O perfil `happy_gold_tick_impulse_shadow` foi isolado no Bot 17. Ele só produz candidato quando a
janela `impulse_30s_ready` está aquecida e o movimento assinado alcança 95,5 pips XAUUSD de 0,01. O sinal
do movimento define Buy ou Sell. A resposta permanece `hold`, sugere lote 0,10 e documenta SL/TP de
240/1.000 pips. O serviço normaliza `_Point` para funcionar também em brokers com três casas
decimais. Candidatos sustentados são deduplicados por minuto.

O Bot 17 não cria paper trades pela engine M5: candles de cinco minutos não conseguem ordenar stop,
alvo e saídas de operações que duram segundos. A avaliação de saída dependerá de um lifecycle tick a
tick separado. `experimental_shadow_lock=true` e as chamadas do EA usam `allowExecution=false`.

### Replay anual de 2025

O dataset Dukascopy de `2025-01-01` a `2026-01-01` contém 365 arquivos diários marcados como
concluídos, 70.318.713 ticks válidos e 2,81 GB de CSV. Não há datas ausentes; 18 de abril é o único
dia útil vazio e coincide com a Sexta-feira Santa. Os arquivos locais ficam em
`.runtime/market-data/dukascopy/xauusd-2025` e não devem ser versionados nem enviados integralmente
ao Supabase.

O replay tick a tick está em `scripts/backtest_happy_gold_tick_impulse.py`. Ele usa Ask para comprar,
Bid para vender, o spread histórico e saídas no preço executável oposto. Os artefatos derivados ficam
em `data/research/tick-backtests`.

O teste rejeitou a hipótese de que o limiar de 95,5 pips seja o gatilho completo. A geometria fixa
gerou 40.479 operações, 32,83% de acerto e profit factor 0,499. A gestão com break-even/trailing gerou
54.284 operações, 25,47% de acerto e profit factor 0,352. Mesmo a hipótese exploratória com rearme e
cooldown de 90 minutos gerou 2.727 operações, 24,17% de acerto e profit factor 0,305. Em contraste, o
forward publicado contém somente 348 operações nos 55 dias disponíveis de 2025, média de 6,3 por
dia e mediana de 109 minutos entre entradas.

Assim, o impulso de 30 segundos permanece um filtro discriminante na amostra de entradas conhecidas,
mas não deve ser tratado como regra de entrada autônoma. Faltam pelo menos uma condição de contexto
ou evento de ativação e a regra real de saída. Esses resultados não devem alimentar o gráfico
comparativo principal até uma nova hipótese reduzir a frequência e sobreviver a validação fora da
amostra.

Com o ano completo, 348 entradas de 2025 receberam timestamp candidato. Somente 123 ficaram em
confiança alta ou média; 170 divergiram materialmente da cotação Dukascopy e 55 não tiveram saída
reconstruível. Nessa amostra, o movimento direcional mediano foi 120,15 pips em 30 segundos e 167,15
pips em 60 segundos. A janela de 60 segundos obteve AUC 0,875 contra controles pareados. O contexto
de 15 minutos foi o atributo mais relacionado ao resultado das entradas conhecidas, mas não
generalizou quando aplicado a todos os cruzamentos do ano.

Modelar spread de 10 pips, rearme e cooldown de 150 minutos melhorou o replay, mas o melhor cenário
continuou negativo: janela de 60 segundos com disparo em 160 pips produziu 1.673 operações, 34,31%
de acerto e profit factor 0,886. Stops virtuais de 30 a 60 pips reproduziram o tamanho das perdas
publicadas, porém reduziram o acerto. Isso separa claramente correlação retrospectiva de uma regra
executável: o histórico público ainda não identifica a fase exata do gatilho nem a gestão de saída.

### ZigZag combinado com contexto de ticks

As regras existentes foram avaliadas causalmente em 123 entradas reconstruídas e 607 controles. O
ZigZag M30 coincidiu na direção com 43 entradas (34,96%), contra somente 11 controles (1,81%). O
Stochastic coincidiu com duas entradas e a Tendência Multitemporal com nenhuma. O ZigZag, portanto,
explica parte relevante da localização do gatilho, mas cobriu vencedoras e perdedoras em proporções
praticamente iguais.

Na amostra conhecida, combinar ZigZag com movimento direcional de 15 minutos de pelo menos 800 pips
produziu 13 vitórias e duas perdas (86,67%). O replay fora dessa seleção rejeitou a regra como
estratégia completa: em 70.318.713 ticks, spread modelado de 10 pips e cooldown de 90 minutos, foram
gerados 390 sinais. Nenhum dos dez cenários de gestão foi lucrativo. O melhor profit factor foi
0,946, com 28,46% de acerto e resultado de -US$ 102,14 (stop de 60 pips e saída em 30 segundos).

O perfil `happy_gold_zigzag_tick_context_shadow` permanece isolado no Bot 18 apenas para diagnóstico
e forward test, com execução bloqueada. Os artefatos estão em
`data/research/happy_gold_existing_contexts_2025.summary.json` e
`data/research/tick-backtests/happy_gold_zigzag_tick_context_2025.summary.json`. A conclusão atual é
que o contexto ZigZag é útil, mas ainda falta um filtro causal capaz de distinguir quais rompimentos
o robô original seleciona.

### Seletor estrutural

No período rotulado, 154 sinais do Bot 18 foram comparados um a um com as entradas reconstruídas;
26 coincidiram em lado e em até 60 segundos. A distância direcional da EMA20 foi o atributo causal
mais discriminante (AUC 0,627). O seletor fixo exclui sexta-feira, exige distância direcional da
EMA20 de pelo menos 900 pips, movimento de 15 minutos de pelo menos 1.000 pips e extensão máxima de
50 pips além do pivô.

Aplicado ao período anterior aos rótulos, de janeiro até 15 de outubro, o seletor produziu 14 sinais,
42,86% de acerto e profit factor 1,782 na geometria stop 60/saída 30 segundos. No ano completo foram
27 sinais, 48,15% de acerto e profit factor 2,653. O resultado permaneceu positivo em oito das dez
gestões já calculadas; os stops de 30 pips foram os casos instáveis. O relatório reproduzível fica em
`data/research/happy_gold_zigzag_selector_holdout_2025.summary.json`.

O perfil `happy_gold_zigzag_structural_tick_shadow` foi criado como Bot 19. A amostra independente
ainda contém apenas 14 operações e é anterior, não posterior, ao período usado para definir o filtro.
Por isso o bot registra somente candidatos, não cria paper trades M5 e permanece bloqueado até obter
forward test em ticks do broker.

A pesquisa de saída avaliou 54 combinações diretamente nos ticks posteriores aos 27 sinais. A
configuração escolhida para telemetria do Bot 19 usa stop virtual de 60 pips, breakeven em 40 pips
com trava de +1, trailing ativado em 40 pips com distância de 20 e encerramento máximo em 60
segundos. No replay, produziu 66,67% de acerto, profit factor 3,092 e drawdown máximo de US$ 16,97,
com resultado positivo em três dos quatro trimestres. O primeiro trimestre contém somente um sinal.
O estudo completo está em `data/research/happy_gold_structural_exit_research_2025.summary.json`.

### Forward lifecycle tick

O Bot 19 usa `tick_shadow_trades`, separado dos paper trades baseados em candles. Ao registrar um
candidato, o serviço abre uma posição simulada com a gestão selecionada e recupera quaisquer ticks
que já tenham chegado ao Supabase desde o timestamp do sinal. Cada lote posterior enviado a
`POST /api/ticks` atualiza melhor preço, stop, breakeven, trailing, alvo e timeout usando Bid para
Buy e Ask para Sell. A operação fechada aparece nos resultados com timeframe `TICK` e identificador
`tick-shadow:`; nenhuma função desse fluxo envia ou modifica ordens no MetaTrader.

Para evitar lacunas, `TickCollectorEA` deve permanecer anexado ao XAUUSD e o serviço
`tick-uploader` deve executar continuamente. Os arquivos são rotacionados a cada cinco segundos; o
uploader e os upserts são idempotentes, e o backfill no momento do candidato cobre a corrida entre
o coletor e a chamada de decisão.

O uploader aceita somente o diretório definido por `DAYTRADE_TICK_FORWARD_COLLECTOR_ID`, cujo padrão
é `2lotus-forward-01`. Exportações sob `2lotus-history-01` permanecem locais e nunca são ingeridas
automaticamente; essa separação evita misturar backfill histórico com a amostra forward.

## Amostra rotulada de 2026

A coleta Dukascopy de 1 de janeiro a 14 de abril de 2026 confirmou `Europe/Helsinki` como a
timezone do histórico: 424 entradas tiveram ticks no minuto publicado, com erro mediano de preço
de 0,008 e 398 correspondências dentro de 0,25. Foram reconstruídas 95 entradas com confiança
alta ou média e comparadas com 470 controles pareados do mesmo dia.

O movimento direcional de 300 segundos foi o discriminador isolado mais forte (AUC 0,866 e
acurácia balanceada leave-one-day-out de 81,8%). As janelas de 60 e 900 segundos atingiram,
respectivamente, 75,1% e 78,3%. O Bot 20 usa essas três janelas como núcleo obrigatório e exige
score mínimo 4/6 incluindo 5, 10 e 30 segundos. Esses números classificam entradas conhecidas
contra controles; ainda não constituem replay financeiro nem autorização para execução.

### Replay exaustivo do Bot 20

A mesma regra foi executada a cada cinco segundos sobre 28.926.579 ticks. O resultado rejeitou a
hipótese: 43.610 operações, 45,97% de acerto, profit factor 0,806 e PnL de -US$ 34.047,50. Rearme
com cooldown não recuperou a regra: 90 minutos produziu PF 0,846 e 150 minutos PF 0,818. O gate
`DAYTRADE_HAPPY_GOLD_MULTIWINDOW_SHADOW_ENABLED` permanece `false`; assim o bot continua visível
para auditoria, mas não registra candidatos nem pode executar ordens.

Esse contraste demonstra que as janelas de impulso descrevem bem os instantes publicados, porém
não explicam o mecanismo que seleciona aproximadamente seis entradas entre centenas de impulsos
diários. A próxima pesquisa deve buscar esse seletor, sem reajustar a gestão de saída.

### Holdout temporal do Bot 19 em 2026

O seletor estrutural do Bot 19 foi preservado sem recalibração e executado nos 28.926.579 ticks de
1 de janeiro a 14 de abril de 2026. O replay causal encontrou 91 sinais. Todos os dez cenários de
saída testados tiveram expectativa positiva: profit factor entre 1,959 e 2,984, com win rate entre
16,48% e 51,65%. Isso confirma portabilidade de expectativa, mas não reproduz os 85% do histórico
publicado.

Uma segunda passagem revalidou os mesmos 91 sinais contra candles M5 completos e aplicou exatamente a
gestão publicada no Bot 19: stop de 60 pips, breakeven em 40 com trava de +1, trailing 40/20 e
timeout de 60 segundos. O resultado foi 51 vitórias e 40 perdas, win rate de 56,04%, profit factor
2,228, PnL modelado de US$ 387,50 e drawdown máximo de US$ 40,67. As duas implementações passaram a
concordar após o filtro de extensão usar o preço executável, como faz o Bot 19, em vez do preço médio.

Os artefatos estão em
`data/research/tick-backtests/happy_gold_zigzag_structural_tick_2026_oos.summary.json`,
`data/research/happy_gold_structural_exit_research_2026_oos.summary.json` e
`data/research/tick-backtests/happy_gold_structural_tick_2026_oos_selected.trades.csv`. O Bot 19
permanece bloqueado para execução; o resultado justifica forward test, não autorização para operar.

### Seletor de range normalizado

O percentil 90 de `range do M5 anterior / ATR14` nas 26 entradas correspondentes de 2025 fixou o
limiar 1,876955 antes da avaliação em 2026. No trecho de 2025 anterior aos rótulos, o filtro reduziu
14 para 10 operações e elevou o profit factor de 2,106 para 2,291. No holdout posterior de 2026,
reduziu 91 para 75 operações, preservou 13 das 14 correspondências com o original e elevou o profit
factor de 2,228 para 2,485. O win rate passou de 56,04% para 57,33%, o PnL foi US$ 380,28 e o
drawdown caiu de US$ 40,67 para US$ 34,22.

O perfil `happy_gold_zigzag_normalized_range_shadow` foi criado como Bot 21, sem alterar o Bot 19.
Ele reutiliza o lifecycle tick stop 60, breakeven 40/+1, trailing 40/20 e timeout 60 segundos. A
execução permanece bloqueada. O relatório reproduzível está em
`data/research/happy_gold_normalized_range_selector_walkforward.summary.json`.

### Micro-saídas

Uma grade de 140 combinações de stop, alvo curto e timeout foi selecionada usando somente os 20
sinais filtrados de 2025. A configuração vencedora no treino, stop 60/alvo 80/timeout 60 segundos,
teve 65% de acerto e profit factor 3,203. Aplicada sem alterações aos 75 sinais de 2026, caiu para
50,67% de acerto, profit factor 1,416 e drawdown de US$ 61,33. O resultado é inferior ao lifecycle
atual do Bot 21 em acerto, profit factor e drawdown; portanto a hipótese foi rejeitada e não originou
novo bot. O relatório está em `data/research/happy_gold_micro_exit_walkforward.summary.json`.

### Holdout posterior até agosto de 2026

Foram coletados mais 29.011.752 ticks Dukascopy entre 15 de abril e 8 de agosto de 2026, período
completamente posterior à definição do Bot 21. O Bot 19 gerou 46 sinais estruturais; o filtro de
range normalizado preservou 39. Com a gestão congelada do Bot 21, foram 20 vitórias e 19 perdas,
51,28% de acerto, profit factor 1,613, PnL de US$ 80,24 e drawdown de US$ 37,51. A expectativa
continuou positiva, mas abaixo do primeiro holdout.

A sessão exploratória 03:00-11:00 UTC, que havia produzido PF 2,94 em 2025 e 3,89 no primeiro
trecho de 2026, foi testada sem alterações. No novo holdout produziu somente 12 operações, 41,67%
de acerto e PF 1,594, sem superar o Bot 21 completo. A sessão foi rejeitada e não originou Bot 22.
O relatório está em `data/research/happy_gold_session_3_11_holdout_2026_apr_aug.summary.json`.

### Robustez de execução

Os 39 sinais do holdout novo foram congelados e reexecutados em 16 combinações de spread 5, 10,
15 e 20 pips com latência de entrada 0, 250, 500 e 1.000 ms. Todos permaneceram lucrativos. No
cenário-base spread 10/latência zero, o PF foi 1,613. O pior caso, spread 20/latência 1.000 ms,
caiu para PF 1,038 e apenas US$ 6,37, indicando margem operacional quase esgotada. Até spread 15 e
latência 500 ms, o pior PF foi 1,249.

O Bot 21 passa a bloquear candidatos com spread acima de 15 pontos/pips e registra meta operacional
de latência até 500 ms. O estudo está em
`data/research/happy_gold_execution_robustness_2026_apr_aug.summary.json`.
