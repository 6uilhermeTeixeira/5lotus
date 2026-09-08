# 2Lotus market data pipeline

Pipeline isolado de coleta e publicação do histórico XAUUSD da Dukascopy usado pelo ambiente de pesquisa 2Lotus.

- `src/lotus/ingestion/dukascopy.py`: coletor horário resumível.
- `scripts/publish-dataset.py`: publicação das partições Parquet e do release corrente.
- `scripts/collection-status.py`: diagnóstico do manifesto compartilhado.

Os dados permanecem fora do repositório em `/home/codexops/lotus-data`.
