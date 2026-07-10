# Railway free tier caps provisioned services, so the one app service runs both
# processes: Celery worker in the background, uvicorn as PID 1. Locally and in
# compose the api/worker Dockerfiles stay separate — this file is Railway-only.
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["sh", "infra/railway_start.sh"]
