# Progress

## Status: not started — scaffold only

Repo created, folder structure matches the dossier spec, no application code written yet.

## Next step

**M1** (per dossier §5 Development plan): EDGAR ingestion + retry/backoff + table-aware parsing.
- Implement `ingestion/fetch_edgar.py` — async fetch, exponential backoff + jitter on 429/5xx,
  dead-letter on retry exhaustion.
- Implement `ingestion/normalize.py` — unify 10-K/10-Q/8-K/transcript into one Document/Section
  schema.
- Get one real filing ingested end-to-end into Postgres before touching anything else.

## Log

- **2026-07-09** — repo scaffolded (folder structure, CLAUDE.md, PROGRESS.md, pyproject.toml,
  docker-compose skeleton, .gitignore). No app code yet.

## Open decisions / deviations from the dossier

(none yet — record anything that changes from the original spec here, with why)
