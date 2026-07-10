#!/bin/sh
# Railway container entrypoint: bootstrap the DB (pgvector extension + Alembic,
# both idempotent), then run Celery worker + API in one container (free-tier
# service cap — see railway.Dockerfile).
set -e

python - <<'PY'
import os
import sqlalchemy

engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
PY

alembic upgrade head

celery -A ingestion.celery_app worker --loglevel=warning --concurrency=1 &
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
