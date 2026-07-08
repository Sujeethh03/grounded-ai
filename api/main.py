"""FastAPI entrypoint. See dossier Ledger Lens §2 "API design" for the full
endpoint table (POST /api/v1/ingest/{cik}, POST /api/v1/query,
GET /api/v1/graph/company/{cik}, /healthz, /readyz).

M1 goal: get /healthz responding from inside docker compose before building
any ingestion logic — proves the container/DB wiring works first.
"""

from fastapi import FastAPI

app = FastAPI(title="Ledger Lens")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
