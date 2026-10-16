# CaseProof backend image: separate processes for the API, worker, dispatcher and setup jobs.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /app/services/backend
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer fonts-liberation fonts-noto-core && rm -rf /var/lib/apt/lists/*
COPY services/backend/pyproject.toml services/backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY services/backend/src ./src
COPY services/backend/migrations ./migrations
COPY services/backend/alembic.ini ./
COPY policies /app/policies
COPY evaluation/results/latest.json /app/evaluation/results/latest.json
COPY evaluation/results/MODEL_CARD.md /app/evaluation/results/MODEL_CARD.md
RUN uv sync --frozen --no-dev && useradd --uid 10001 --create-home caseproof
USER caseproof
ENV PATH="/app/services/backend/.venv/bin:$PATH" CASEPROOF_ENVIRONMENT=cloud CASEPROOF_DEV_IDENTITY=false
EXPOSE 8080
CMD ["sh", "-c", "case \"$ROLE\" in \
  api) exec uvicorn caseproof.api.app:app --host 0.0.0.0 --port 8080 ;; \
  worker) exec uvicorn caseproof.worker:app --host 0.0.0.0 --port 8080 ;; \
  dispatcher) exec python -m caseproof.dispatcher ;; \
  migrate) exec alembic upgrade head ;; \
  seed) exec python -m caseproof.seed $SEED_ARGS ;; \
  *) echo 'set ROLE to api, worker, dispatcher, migrate or seed'; exit 2 ;; esac"]
