# Progress

## Status: GroundedAI pivot COMPLETE — two live domains, graph multi-hop proven, 20-case eval run

**What GroundedAI is now:** a verifiable agentic retrieval platform with two document sources —
FDA drug labels (headline) and SEC filings (kept as proof of source-agnosticism). Renamed from
"Ledger Lens" on 2026-07-10; see CLAUDE.md's history note for the recorded rationale.

**Eval numbers (2026-07-10, 20 cases: 10 SEC + 10 drug, gpt-4o-mini + text-embedding-3-small):**
- **refusal_correctness 0.95** (19/20 — only miss is the long-known q3 SEC legal-proceedings
  over-refusal), **citation_validity 1.00**, **keyword_coverage 0.88**.
- All 10 drug cases passed, including both graph-routed cases and all 3 refusal-expected ones.
- These numbers fill the resume bullet placeholders. Re-run with `python -m evals.run_eval`.

**Corpus (local DB):** 12 SEC filings (Apple, JPMorgan, Tesla) → 156 chunks; 17 drug labels
(warfarin, aspirin, ibuprofen, lisinopril, metformin, atorvastatin, omeprazole, fluoxetine,
amlodipine) → 425 chunks. Graph: 3 Companies, 12 Filings, 18 DISCUSSES; 9 Drugs, 11 Conditions
max, 47 TREATS, 22 INTERACTS_WITH.

## The pivot, in commit order (all landed 2026-07-10)

1. **Schema generalization** (`a930058`): filings → source-agnostic `documents` +
   `document_sections` with `source_type` ('sec_filing'|'drug_label'), generic
   entity_id/entity_name/doc_type/source_key/year, `meta` JSONB. Hand-written Alembic
   migration incl. constraint/index renames; live data survived (verified).
2. **openFDA source adapter** (`99b58da`): fetcher (rate-limited, retry/backoff,
   404-NOT_FOUND = "no such drug" never retried, dedupe to newest per set_id), normalizer
   (JSON fields → unified sections, PLR + OTC vocabularies, `canonical_drug_name` strips salt
   suffixes so WARFARIN SODIUM ≡ warfarin), drift rules (label must have ≥3 sections and
   Indications/Purpose), pipeline with two-tier idempotency (same version skips, newer version
   replaces via cascade), Celery task, POST /api/v1/ingest/drug/{name}. Proven live end-to-end
   including through the worker (amlodipine).
3. **Drug graph arm** (`fb257bd`): Drug + Condition nodes only (5 node types total, per-domain
   budget in CLAUDE.md). Deterministic extraction: drug-name lexicon built from the corpus's
   own openFDA metadata; 11-condition taxonomy. INTERACTS_WITH = one edge per unordered pair,
   queried undirected, source set_id as provenance. Three new parameterized Cypher lookups in
   graph_agent incl. the justifying multi-hop (treats X AND interacts with Y); planner prompt
   is now domain-neutral with a two-arg lookup (arg + arg2). **Live proof:** "Which drugs that
   treat pain have a labeled interaction with warfarin?" → "Aspirin and Ibuprofen [C1]" via a
   zero-sub-query pure-graph plan.
   - Bug found & fixed en route: `MERGE ... ON CREATE SET display_name` left the property null
     when an interaction edge created the Drug node before its own label was processed →
     loader now plain-SETs, Cypher coalesce()s.
4. **Eval doubled** (see numbers above).
5. **Rename to GroundedAI**: pyproject (grounded-ai 0.2.0), README, CLAUDE.md, this file,
   DEMO.md, .env.example, scripts/ingest_drug.py CLI added. API surface renamed:
   /api/v1/ingest/sec/{cik}, /api/v1/ingest/drug/{name}, /api/v1/documents (?source_type=).

## What was already built (pre-pivot, all still working)

- **M1/M2 SEC ingestion**: EDGAR client (8 req/s, tenacity retry, 403=config error), HTML→Item
  sections, OCR fallback (real Tesseract, confidence propagated to chunks), drift flagging.
- **M3 retrieval**: paragraph-packing chunker (~3000/300), OpenAI embeddings behind a Protocol,
  one doc_chunks table serving tsvector+GIN and pgvector+HNSW, RRF fusion (k=60).
- **M5 agents**: JSON-mode + pydantic + one-repair LLM harness; planner → retriever ([Cn]
  labels) → synthesis (every-sentence-cited or INSUFFICIENT_EVIDENCE) → deterministic guardrail;
  LangGraph state machine with zero-chunk early refusal, one revision loop, hard refusal.
- **M6 evals + CI**: deterministic harness (gate 0.7 refusal, tripwire 1.0 citation); CI runs
  ruff + tests with tesseract.
- **API layer**: /healthz, /readyz (real dependency checks), /metrics (Prometheus), async
  ingest via Celery/Redis (acks_late, prefetch=1), task status, query endpoint.
- **Deploy prep**: working Dockerfiles, .dockerignore, read-only demo mode (INGEST_ENABLED).

**64 tests passing** (was 46 pre-pivot), ruff clean.

## NOT done yet (be honest about these)

1. **GitHub repo still named ledger-lens** — rename to grounded-ai pending (gh repo rename;
   redirects preserve old links). Local folder name likewise.
2. **Cross-encoder reranking**: baseline numbers exist; needs torch/sentence-transformers.
3. **RAGAS faithfulness** on top of the deterministic harness.
4. **Semantic support-checking in guardrail**: coverage-only today; "does the cited chunk
   actually support the sentence" needs a second LLM pass — next hardening step.
5. **Docker images not rebuilt/tested since the pivot** (they were verified pre-pivot).
6. **Deployment**: no live URL yet (Railway planned — see DEMO.md Path B).
7. **Retrieval quality items**: q3 SEC over-refusal; lexical arm returns 0 hits on
   full-question queries (websearch_to_tsquery ANDs all terms) — dense arm carries those;
   candidate fix: keyword-extract before tsquery.
8. **WebSocket streaming + Next.js citation-viewer UI**: dossier frontend scope, not started.
9. **Condition taxonomy is 11 topics** — fine for 9 drugs; revisit if the corpus grows.

## Next session should

1. Rename the GitHub repo + local folder (5 min), rebuild Docker images against the new
   code, then deploy (Railway) — DEMO.md Path B depends on it.
2. Investigate q3 over-refusal + lexical-arm keyword extraction (cheap, improves the
   headline eval numbers).
3. **Sujeeth must read the whole codebase and be quizzed on it** — the repo is further ahead
   of his ability to defend it than ever after the pivot. Priority reading order in DEMO.md.

## Log

- **2026-07-09** — repo scaffolded as ledger-lens, pushed to github.com/Sujeethh03/ledger-lens.
  M1-M6 + API layer built and live-proven against real EDGAR data; first eval numbers.
- **2026-07-09** — deploy prep: Dockerfiles verified, DEMO.md runbook, read-only demo mode.
- **2026-07-10** — **GroundedAI pivot**: schema generalized to multi-source documents; openFDA
  drug-label adapter built + live-proven; drug graph arm (Drug/Condition, TREATS/INTERACTS_WITH)
  with live multi-hop; eval set doubled to 20 (0.95/1.00/0.88); renamed from Ledger Lens.

## Open decisions / deviations from the dossier

- **The pivot itself** — recorded in CLAUDE.md's history note (drug labels headline, SEC kept).
- `DocumentSection` table (normalized text needs a home before chunking) — M1, name updated.
- `ingestion_status` lifecycle: pending → indexed only after real chunking/embedding — M1.
- Custom eval harness instead of RAGAS (deterministic first, judged metrics later) — M6.
- Guardrail is coverage-only, not support-checking, for now — M5.
- Graph extraction stays deterministic (lexicon/taxonomy, no LLM) in both domains — reliability
  over flexibility for graph ground truth.
- Postgres role/db still named `ledgerlens` post-rename — implementation detail, not worth a
  migration.
- pip on this machine needs `--index-url https://pypi.org/simple` (global CodeArtifact index
  with expired token; left untouched deliberately).
