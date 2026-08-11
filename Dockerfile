FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATABASE_URL=sqlite:////data/database.db \
    WEB_CONCURRENCY=2

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY alembic.ini .
COPY migrations ./migrations
COPY centropic ./centropic
COPY services ./services
COPY templates ./templates
COPY static ./static
COPY scripts ./scripts
COPY workers ./workers
COPY translations ./translations
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN mkdir -p /data /app/instance \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /data \
    && chmod +x /docker-entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
