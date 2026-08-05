# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

# Evita .pyc, força stdout sem buffer (logs em tempo real no docker logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências de sistema mínimas para Pillow (libjpeg/zlib) e healthcheck (curl)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Usuário não-root (boa prática de segurança em containers)
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/instance/uploads/templates \
                /app/instance/uploads/photos \
                /app/instance/uploads/generated \
    && chown -R appuser:appuser /app \
    && chmod +x /app/entrypoint.sh

USER appuser

EXPOSE 5002

# Usa o PORT do ambiente (definido no .env), com 5002 de padrão — assim mudar a
# porta no .env não quebra o healthcheck.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-5002}/healthz" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
