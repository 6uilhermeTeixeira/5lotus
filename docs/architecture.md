# Arquitetura inicial recomendada

## Recomendacao

Arquitetura hibrida:

1. `Expert Advisor MQL5` dentro do MT5
2. `Python strategy service` rodando no Linux
3. `HTTP local` como canal entre execucao e estrategia

## Motivo

Essa separacao respeita melhor as restricoes do ambiente:

- MT5 executa no runtime que ele suporta
- Python roda nativamente no Linux desta maquina
- a estrategia pode evoluir sem acoplar a logica ao terminal

## Fluxo

```text
MT5 terminal
  -> Expert Advisor MQL5
    -> coleta estado do mercado / conta / posicoes
    -> envia contexto para Python local
Python strategy service
  -> aplica estrategia
  -> aplica risco
  -> responde: buy / sell / close / hold
Expert Advisor MQL5
  -> valida resposta
  -> envia ordem no MT5
  -> registra resultado
```

## Componentes

### 1. MT5 / MQL5

Responsabilidades:

- receber ticks e eventos de mercado
- montar contexto minimo da decisao
- executar ordens
- confirmar fills, rejeicoes e posicoes
- fazer retry controlado apenas quando explicitamente permitido

### 2. Python strategy service

Responsabilidades:

- gerar sinal
- validar horario e sessao
- validar limites de risco
- aplicar filtros de spread, volatilidade e exposicao
- expor endpoints locais de saude e decisao

### 3. Persistencia

Fase 1:

- SQLite local ou Postgres em Docker

Registros minimos:

- market snapshots relevantes
- sinais emitidos
- ordens solicitadas
- ordens executadas
- erros
- metricas de risco

## Alternativas avaliadas

### Opcao A: tudo em MQL5

Vantagem:

- execucao mais simples dentro do MT5

Desvantagem:

- pior ergonomia para testes, analytics e evolucao do modelo

### Opcao B: Python falando direto com MetaTrader5

Vantagem:

- stack unica em Python

Desvantagem:

- neste host Linux depende de Wine + terminal + setup mais fragil
- maior risco operacional para um primeiro ciclo

## Decisao inicial

Comecar com:

- `MQL5` para execucao
- `Python` para estrategia e risco

Se depois o ambiente Wine ficar robusto e controlado, podemos reavaliar a interface Python direta com o terminal.
