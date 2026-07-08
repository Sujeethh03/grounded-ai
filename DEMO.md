# Interview Demo Runbook

Two demo paths. Practice Path A once tonight; keep Path B warm as the fallback.
**Rule: never debug live in an interview.** If something breaks, switch paths and keep talking.

## Path A — local full stack (everything works today; zero dependencies on cloud)

### Pre-interview checklist (do 15 min before)

```bash
brew services start postgresql@17 redis neo4j     # all three must be running
cd ~/ledger-lens && source .venv/bin/activate
pytest -q                                          # 46 passed = green light
celery -A ingestion.celery_app worker --loglevel=warning &   # terminal 1
uvicorn api.main:app --port 8000 &                            # terminal 2
curl -s localhost:8000/readyz                      # {"status":"ready",...}
```

### The 5-minute demo arc (in this order — it tells a story)

1. **Async ingestion** — "the system pulls real SEC filings through a queue":
   ```bash
   curl -s -X POST "localhost:8000/api/v1/ingest/1018724?limit=3"   # Amazon — new company, live
   curl -s localhost:8000/api/v1/tasks/<task_id-from-above>
   curl -s localhost:8000/api/v1/filings | python3 -m json.tool | head -30
   ```
   Say: webhook-style 202-immediately, Celery worker does the slow work, idempotent by
   accession number, rate-limited to SEC's fair-access limit with backoff + retries.

2. **Cited agent answer** — the headline:
   ```bash
   python -m scripts.ask "What supply chain risks does Apple disclose in its recent filings?"
   ```
   Say: planner decomposes → hybrid search (BM25 + pgvector fused with RRF) → synthesis must
   cite every sentence → a deterministic guardrail verifies every citation or the answer is
   refused. Point at the [Cn] labels mapping to real accession numbers.

3. **The graph arm** — cross-company question:
   ```bash
   python -m scripts.ask "Which companies discuss supply chain risks in their filings?"
   ```
   Say: planner routed this to Neo4j — parameterized Cypher only, no LLM-written queries —
   and the graph fact enters the same citation system as text chunks.

4. **Refusal** — the thing most RAG demos can't do:
   ```bash
   python -m scripts.ask "What was Tesla's total revenue in fiscal year 2019?"
   ```
   Say: not in the corpus → the system says so instead of hallucinating. Eval numbers:
   refusal_correctness 0.90, citation_validity 1.00 on a 10-case golden set, gate-checked.

5. **Production surface** (if time): `curl localhost:8000/metrics | head`, show
   Prometheus counters; mention structured JSON logs, /readyz dependency checks, CI history
   including the three red runs (tesseract missing on the runner — environment parity lesson).

## Path B — cloud URL (Railway)

Same arc, swap `localhost:8000` for the Railway URL. **Warm it up 10 minutes before the
interview** (hit /readyz and one /query). If the cloud misbehaves mid-demo: "let me show you
on the local stack — same containers, same compose file" → Path A. That sentence sounds
senior, not embarrassed.

## Questions to expect (short answers you must own)

- **Why pgvector over Pinecone?** One datastore for chunks + metadata + lexical search;
  hybrid = SQL join away; no second system to keep in sync at this scale.
- **Why RRF not weighted scores?** BM25 and cosine scores aren't on comparable scales;
  RRF fuses ranks, needs no tuning, is the standard baseline.
- **Why is the guardrail deterministic?** The writer and checker must be different systems;
  a regex over [Cn] labels can't be sweet-talked. Semantic support-checking is the known
  next layer.
- **Why no LLM-written Cypher?** The graph is the auditable arm — parameterized queries
  can't hallucinate structure. Flexibility lives in the text-RAG arm.
- **What breaks at 100x scale?** Embedding cost (cache + incremental), Postgres HNSW memory
  (partition by year/company), per-tenant rate limiting on the API, worker autoscaling by
  queue depth.
- **What's honestly unfinished?** Reranking (baseline measured first, deliberately),
  semantic support-check, Person nodes need DEF 14A ingestion, one eval case over-refuses.
  Saying this unprompted builds more trust than hiding it.

## Tonight, after deploy: read the code

30 minutes minimum: `agents/graph.py` → `agents/guardrail_agent.py` →
`retrieval/hybrid_search.py` → `ingestion/pipeline.py`. Every docstring contains the "why"
for that module. If you can re-draw the graph flow from memory on paper, you're ready.
