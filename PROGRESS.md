# Progress

## Status: ALL core milestones built and demonstrated — M1-M6 + API layer, real LLM runs done

**Real run results (2026-07-09, gpt-4o-mini + text-embedding-3-small):**
- Indexed: 12 filings → 156 chunks (Apple, JPMorgan, Tesla).
- `scripts.ask` works end-to-end: planner decomposition → hybrid retrieval → every-sentence-cited
  answer → guardrail pass. Verified against real Apple 10-Q content.
- **Eval numbers (evals/run_eval.py, 10 cases): refusal_correctness 0.90, citation_validity 1.00,
  keyword_coverage 0.88.** Known failure: q3 (legal proceedings) over-refused — conservative
  direction, but a retrieval-quality item to investigate.
- Observed: lexical arm often returns 0 hits for full-question queries (websearch_to_tsquery ANDs
  all terms) — dense arm carries those. Improvement candidate: keyword-extract before ts_query.

**M4 knowledge graph (built + demonstrated live, same day):**
- Neo4j installed (brew), graph loaded: 3 companies, 12 filings, 18 DISCUSSES edges.
- `ingestion/entity_extraction.py`: deterministic risk-topic taxonomy matcher (10 topics) —
  deliberate deviation from LLM extraction (reliability > flexibility for graph ground truth);
  Person/BOARD_MEMBER_OF nodes deferred until DEF 14A proxy statements are ingested.
- `ingestion/graph_loader.py` (idempotent MERGE sync) + `scripts/load_graph.py`.
- `agents/graph_agent.py`: parameterized Cypher only (no LLM-written Cypher — auditable arm);
  graph facts rendered as SearchHit sources entering the same [Cn] citation system.
- Planner extended: optional graph_lookups routing; sub_queries may be empty for pure-graph
  questions (schema validator requires ≥1 retrieval arm). Dead Neo4j degrades gracefully —
  graph augments retrieval, never breaks it (tested).
- Live proof: "Which companies discuss supply chain risks?" → graph fact cited as [C1] +
  text chunks as supporting citations in one guardrail-passed answer.

**API layer (built after M6, proven live end-to-end)**
- `ingestion/celery_app.py` + `ingestion/tasks.py`: Celery over Redis (acks_late,
  prefetch=1), thin tasks wrapping the proven pipeline functions.
- `api/main.py`: /healthz, /readyz (real Postgres+Redis checks), /metrics (Prometheus
  counters + latency histograms via middleware, JSON structured request logs),
  POST /api/v1/ingest/{cik} (202 + task id), GET /api/v1/tasks/{id},
  GET /api/v1/filings, POST /api/v1/query (503 until OPENAI_API_KEY set).
- **Live proof**: started worker + uvicorn, POSTed ingest for Tesla (CIK 1318605) →
  task went through Redis → worker pulled 3 real filings from EDGAR → SUCCESS state with
  result via GET /api/v1/tasks → Tesla visible in /api/v1/filings. Redis installed via brew.
- 38 tests passing (API tests mock the queue; readyz/filings covered by the live run).

## What's built

**M1 — ingestion (verified against real EDGAR data)**
- `ingestion/fetch_edgar.py`: async EDGAR client, 8 req/s rate limit, tenacity retry
  (backoff+jitter) on 429/5xx, 403 = fatal config error. Returns bytes (PDF sniffing needs raw).
- `ingestion/normalize.py`: HTML → text → Item-header sections, Full Text fallback.
- `ingestion/pipeline.py` + `scripts/ingest.py`: idempotent by accession number.
- Real data in local DB: Apple (5 filings) + JPMorgan (4 filings).

**M2 — ingestion hardening**
- `ingestion/schema_drift.py`: structural expectation check per form type; bad parses get
  `schema_drift_flagged`, never silently indexed.
- `ingestion/ocr_fallback.py`: PDF sniff → pypdfium2 render → Tesseract OCR with mean word
  confidence persisted (filings.ocr_confidence → propagates to chunks).
- OCR test generates a real image-only PDF and runs actual Tesseract (not mocked).

**M3 — retrieval**
- `retrieval/chunking.py`: paragraph-packing chunker (~3000 chars, 300 overlap).
- `retrieval/embeddings.py`: OpenAI text-embedding-3-small behind an `Embedder` Protocol.
- Migration 3: `doc_chunks` has generated tsvector column + GIN index + HNSW (cosine) index —
  both hybrid arms served by one Postgres table.
- `retrieval/hybrid_search.py`: websearch_to_tsquery + cosine, RRF fusion (k=60).
- `retrieval/indexer.py`: indexes pending/ocr_fallback filings, refuses drift-flagged ones.
- CLIs: `scripts/index.py`, `scripts/search.py`.

**M5 — agents (LangGraph)**
- `agents/llm.py`: mini harness — JSON-mode + pydantic validation + one error-fed repair
  attempt; env-driven model tiers (CHEAP_MODEL / SYNTHESIS_MODEL, defaults gpt-4o-mini).
- `agents/planner.py` → `agents/retriever_agent.py` ([Cn] labeling) → `agents/synthesis_agent.py`
  (every-sentence-cited contract or INSUFFICIENT_EVIDENCE) → `agents/guardrail_agent.py`
  (deterministic coverage check).
- `agents/graph.py`: StateGraph — zero-chunk early refusal, one revision loop fed real
  violations, hard refusal over returning a failed answer. CLI: `scripts/ask.py`.

**M6 — evals + CI**
- `evals/golden_qa.jsonl`: 10 cases (7 answerable, 3 refusal-expected) matched to the corpus.
- `evals/run_eval.py`: refusal_correctness (gate 0.7), citation_validity (tripwire 1.0),
  keyword_coverage. Runs locally: `python -m evals.run_eval`.
- CI installs tesseract, runs ruff + 32 tests.

## NOT done yet (be honest about these)

1. **Cross-encoder reranking**: now unblocked — RRF-only eval numbers exist (see above), so a
   reranker's improvement can be measured against them. Needs torch/sentence-transformers.
2. **RAGAS**: layer faithfulness scoring on top of the deterministic harness.
3. **Semantic support-checking in guardrail**: coverage-only today; "does the cited chunk
   actually support the sentence" needs a second LLM pass — next hardening step.
4. **Person/BOARD_MEMBER_OF graph nodes**: needs DEF 14A proxy statement ingestion.
5. **Docker compose stack**: written, untested — needs Docker Desktop (or colima) installed.
6. **Deployment**: no live demo URL yet — needs a host decision (Fly.io/Railway/EC2) + account.
7. **WebSocket streaming + Next.js citation-viewer UI**: dossier frontend scope, not started.
8. **Retrieval quality items**: q3 over-refusal; lexical-arm zero-hits on full-question queries.

## Next session should

1. Investigate q3 over-refusal + lexical-arm behavior (cheap, improves eval numbers).
2. Then pick: reranking (measurable now) / Docker verification / deployment / support-checker.
3. Sujeeth should read the whole codebase and be quizzed on it — the repo is ahead of his
   ability to defend it in an interview, and that gap matters more than new features.

## Log

- **2026-07-09** — repo scaffolded, pushed to github.com/Sujeethh03/ledger-lens (public).
- **2026-07-09** — M1 built + verified end-to-end against real SEC EDGAR data.
- **2026-07-09** — M2 (drift + OCR), M3 (chunk/embed/hybrid), M5 (agent graph), M6 (evals + CI)
  built with 32 passing tests. Real LLM runs + eval numbers pending API key. gh CLI installed
  and authenticated; Postgres 17 + pgvector + tesseract installed locally via Homebrew.

## Open decisions / deviations from the dossier

- `FilingSection` table added (normalized text needs a home before chunking) — M1.
- `ingestion_status` lifecycle: pending → indexed only after real chunking/embedding — M1.
- Custom eval harness instead of RAGAS (deterministic first, judged metrics later) — M6.
- Guardrail is coverage-only, not support-checking, for now — M5.
- pip on this machine has a global QuantJo CodeArtifact index configured
  (~/.config/pip/pip.conf) with an expired token — every pip install in this repo must use
  `--index-url https://pypi.org/simple`. Left the global config untouched deliberately.
