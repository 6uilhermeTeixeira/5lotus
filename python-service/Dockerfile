FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

COPY app ./app
COPY scripts ./scripts
COPY data/bots.json ./data/bots.json
COPY data/legacy-bots.json ./data/legacy-bots.json
COPY data/backtests ./data/backtests
COPY data/backtests-operational ./data/backtests-operational

RUN useradd --create-home --uid 10001 lotus && chown -R lotus:lotus /app
USER lotus

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "7775"]
