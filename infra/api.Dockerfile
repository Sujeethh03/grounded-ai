# Single-stage on purpose: `pip install .` needs the package source present,
# and the previous "copy pyproject first" split installed the project before
# its packages existed. Optimize layers later; correct beats clever tonight.
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8000
# PORT is injected by Railway/Render/Fly; 8000 for local + compose
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
