# Disposable frozen native Linux proof; no credentials/providers, not a deployment.
FROM ghcr.io/astral-sh/uv:0.11.27 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY services/api/pyproject.toml services/api/uv.lock /app/services/api/
COPY services/api/buyeros_api /app/services/api/buyeros_api
COPY services/worker/pyproject.toml services/worker/uv.lock /app/services/worker/
COPY services/worker/buyeros_worker /app/services/worker/buyeros_worker
COPY services/api/tools/probe_worker_runtime.py /app/services/api/tools/
RUN uv sync --frozen --project services/worker --no-dev
RUN uv sync --frozen --project services/api --no-dev
ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "--project", "services/worker", "python", "services/api/tools/probe_worker_runtime.py"]
