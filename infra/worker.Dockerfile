FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
CMD ["celery", "-A", "ingestion.celery_app", "worker", "--loglevel=info"]
