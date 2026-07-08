"""Celery application — Redis as broker and result backend.

Worker entrypoint (matches infra/worker.Dockerfile):
    celery -A ingestion.celery_app worker --loglevel=info
"""

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery("ledger_lens", broker=REDIS_URL, backend=REDIS_URL, include=["ingestion.tasks"])

app.conf.update(
    task_acks_late=True,  # a worker crash mid-task requeues it instead of losing it
    worker_prefetch_multiplier=1,  # long-running tasks: don't hoard queue items
    task_track_started=True,
    result_expires=3600,
)
