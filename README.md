# Ledger Lens

Multi-source financial-document intelligence pipeline — see `CLAUDE.md` for the full project
context and the [Portfolio Dossier](https://claude.ai/code/artifact/fe962bed-b7aa-4334-8893-90dc5c8c070f)
for the complete architecture, schema, and milestone plan.

## Local dev

```bash
cp .env.example .env   # fill in secrets
docker compose -f infra/docker-compose.yml up -d postgres neo4j redis
pip install -e ".[dev]"
alembic upgrade head
uvicorn api.main:app --reload
```

## Status

See `PROGRESS.md`.
