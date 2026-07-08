"""FastAPI application — the dossier's Ledger Lens API surface (minus M4 graph
routes, deferred with Neo4j).

Endpoints:
    GET  /healthz                       liveness (process is up, nothing else)
    GET  /readyz                        readiness — real DB + Redis checks
    GET  /metrics                       Prometheus scrape
    POST /api/v1/ingest/{cik}           enqueue async ingestion -> 202 + task id
    GET  /api/v1/tasks/{task_id}        Celery task status/result
    GET  /api/v1/filings                filings + ingestion_status (drift/OCR visible here)
    POST /api/v1/query                  full agent pipeline -> cited answer
"""

import os
import time

import structlog
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from db.models import Filing  # noqa: E402
from db.session import get_session  # noqa: E402

structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()])
log = structlog.get_logger(__name__)

app = FastAPI(title="Ledger Lens", version="0.1.0")

REQUEST_COUNT = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["method", "path"])


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    path = request.scope.get("route").path if request.scope.get("route") else request.url.path
    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
    log.info("request", method=request.method, path=path, status=response.status_code, duration_ms=round(elapsed * 1000, 1))
    return response


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    problems: dict[str, str] = {}
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        problems["postgres"] = str(exc)
    try:
        import redis

        redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0")).ping()
    except Exception as exc:
        problems["redis"] = str(exc)

    if problems:
        raise HTTPException(status_code=503, detail=problems)
    return {"status": "ready", "postgres": "ok", "redis": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class IngestResponse(BaseModel):
    task_id: str
    status: str = "queued"


@app.post("/api/v1/ingest/{cik}", status_code=202, response_model=IngestResponse)
def trigger_ingest(cik: str, limit: int = 5):
    if not cik.isdigit():
        raise HTTPException(status_code=422, detail="CIK must be numeric")
    from ingestion.tasks import ingest_company_task

    result = ingest_company_task.delay(cik, limit=limit)
    log.info("ingest_enqueued", cik=cik, task_id=result.id)
    return IngestResponse(task_id=result.id)


@app.get("/api/v1/tasks/{task_id}")
def task_status(task_id: str):
    from ingestion.celery_app import app as celery_app

    async_result = celery_app.AsyncResult(task_id)
    payload = {"task_id": task_id, "state": async_result.state}
    if async_result.successful():
        payload["result"] = async_result.result
    elif async_result.failed():
        payload["error"] = str(async_result.result)
    return payload


@app.get("/api/v1/filings")
def list_filings():
    with get_session() as session:
        filings = session.scalars(select(Filing).order_by(Filing.filing_date.desc())).all()
        return [
            {
                "id": str(f.id),
                "company": f.company_name,
                "cik": f.company_cik,
                "form_type": f.form_type,
                "fiscal_year": f.fiscal_year,
                "accession_number": f.accession_number,
                "ingestion_status": f.ingestion_status,
                "ocr_confidence": float(f.ocr_confidence) if f.ocr_confidence is not None else None,
            }
            for f in filings
        ]


class QueryRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)


class QueryResponse(BaseModel):
    answer: str
    refused: bool
    sub_queries: list[str]
    sources: list[dict]


@app.post("/api/v1/query", response_model=QueryResponse)
def query(body: QueryRequest):
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured on the server")
    from agents.graph import ask
    from agents.llm import OpenAIChat
    from retrieval.embeddings import OpenAIEmbedder

    result = ask(body.question, OpenAIChat(), OpenAIEmbedder())
    return QueryResponse(
        answer=result.answer,
        refused=result.refused,
        sub_queries=result.sub_queries,
        sources=[
            {
                "label": c.label,
                "company": c.hit.company_name,
                "form_type": c.hit.form_type,
                "fiscal_year": c.hit.fiscal_year,
                "section": c.hit.section,
                "accession_number": c.hit.filing_accession,
            }
            for c in result.citations
        ],
    )
