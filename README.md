# Ledger Lens

Multi-source financial-document intelligence: SEC filings ingested through a fault-tolerant
async pipeline (retry/backoff, OCR fallback, schema-drift flagging), indexed for hybrid
retrieval (BM25 + pgvector, RRF fusion), and answered by a LangGraph agent pipeline that
must cite every sentence — or refuse.

Full architecture and milestone plan: `CLAUDE.md` + the
[Portfolio Dossier](https://claude.ai/code/artifact/fe962bed-b7aa-4334-8893-90dc5c8c070f).
Current status: `PROGRESS.md`.

## Stack

FastAPI · Celery + Redis · PostgreSQL + pgvector (one store, both retrieval arms) ·
Neo4j knowledge graph (risk-topic entities, parameterized-Cypher-only agent arm) ·
LangGraph · OpenAI (embeddings + cost-tiered chat) · Tesseract OCR · Prometheus metrics

Measured (10-case golden QA eval): refusal_correctness 0.90 · citation_validity 1.00 ·
keyword_coverage 0.88

## Quickstart (local)

```bash
# services: Postgres 17 + pgvector, Redis (brew services start postgresql@17 redis)
cp .env.example .env         # add your OPENAI_API_KEY + a real SEC_EDGAR_USER_AGENT
python3 -m venv .venv && source .venv/bin/activate
pip install --index-url https://pypi.org/simple -e ".[dev]"
alembic upgrade head

# CLI path
python -m scripts.ingest --cik 320193 --limit 5    # fetch + normalize Apple filings
python -m scripts.index                            # chunk + embed (needs OPENAI_API_KEY)
python -m scripts.search "supply chain risks"      # hybrid search
python -m scripts.ask "What supply chain risks does Apple disclose?"  # cited answer
python -m evals.run_eval                           # golden-QA eval

# API path
celery -A ingestion.celery_app worker --loglevel=info &
uvicorn api.main:app --port 8000
curl -X POST "localhost:8000/api/v1/ingest/1318605?limit=3"   # async ingest via queue
curl localhost:8000/api/v1/filings
curl -X POST localhost:8000/api/v1/query -H 'content-type: application/json' \
     -d '{"question": "What supply chain risks does Apple disclose?"}'
```

## Tests

```bash
pytest -q        # 38 tests; OCR test runs real Tesseract (brew install tesseract)
ruff check .
```
