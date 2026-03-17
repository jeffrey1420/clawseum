# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12
ARG SERVICE_PATH=gateway

FROM python:${PYTHON_VERSION}-slim AS builder
ARG SERVICE_PATH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && python -m venv ${VIRTUAL_ENV} \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
WORKDIR /build

COPY backend /build/backend

RUN set -eux; \
    req_files=""; \
    [ -f /build/backend/requirements.txt ] && req_files="$req_files /build/backend/requirements.txt" || true; \
    [ -f "/build/backend/${SERVICE_PATH}/requirements.txt" ] && req_files="$req_files /build/backend/${SERVICE_PATH}/requirements.txt" || true; \
    if [ -n "$req_files" ]; then \
      pip install --upgrade pip wheel setuptools && pip install $req_files; \
    else \
      pip install --upgrade pip wheel setuptools && \
      pip install fastapi "uvicorn[standard]" "psycopg[binary]" redis; \
    fi

FROM python:${PYTHON_VERSION}-slim AS runtime
ARG SERVICE_PATH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    SERVICE_PATH=${SERVICE_PATH} \
    APP_MODULE=main:app \
    APP_PORT=8000 \
    BACKEND_RELOAD=0

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY backend /app/src

ENV PYTHONPATH="/app/src:/app/src/${SERVICE_PATH}"

EXPOSE 8000

CMD ["sh", "-c", "if [ \"${BACKEND_RELOAD}\" = \"1\" ]; then RELOAD='--reload'; else RELOAD=''; fi; uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${APP_PORT} ${RELOAD}"]
