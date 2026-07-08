"""M3: chunk + embed ingested filings into doc_chunks.

Only 'pending' and 'ocr_fallback' filings get indexed — 'schema_drift_flagged'
is deliberately excluded (a bad parse in the index poisons retrieval quality
invisibly; that's the whole reason the flag exists). OCR'd filings ARE indexed
but carry filing.ocr_confidence down onto every chunk so retrieval/synthesis
can discount low-quality text.
"""

import structlog
from sqlalchemy import select

from db.models import DocChunk, Filing, FilingSection, IngestionStatus
from db.session import get_session
from retrieval.chunking import chunk_section
from retrieval.embeddings import Embedder

log = structlog.get_logger(__name__)

INDEXABLE_STATUSES = (IngestionStatus.PENDING.value, IngestionStatus.OCR_FALLBACK.value)


def index_pending_filings(embedder: Embedder) -> dict[str, int]:
    summary = {"filings_indexed": 0, "chunks_created": 0, "skipped_flagged": 0}

    with get_session() as session:
        flagged = session.scalars(
            select(Filing).where(Filing.ingestion_status == IngestionStatus.SCHEMA_DRIFT_FLAGGED.value)
        ).all()
        summary["skipped_flagged"] = len(flagged)

        filings = session.scalars(
            select(Filing).where(Filing.ingestion_status.in_(INDEXABLE_STATUSES))
        ).all()

        for filing in filings:
            sections = session.scalars(
                select(FilingSection)
                .where(FilingSection.filing_id == filing.id)
                .order_by(FilingSection.section_index)
            ).all()

            chunks = []
            for section in sections:
                chunks.extend(chunk_section(section.section_name, section.text, start_index=len(chunks)))
            if not chunks:
                log.warning("filing_produced_no_chunks", accession=filing.accession_number)
                continue

            vectors = embedder.embed([c.text for c in chunks])
            for chunk, vector in zip(chunks, vectors):
                session.add(
                    DocChunk(
                        filing_id=filing.id,
                        section=chunk.section_name,
                        chunk_index=chunk.chunk_index,
                        chunk_text=chunk.text,
                        embedding=vector,
                        ocr_confidence=filing.ocr_confidence,
                    )
                )
            filing.ingestion_status = IngestionStatus.INDEXED.value
            summary["filings_indexed"] += 1
            summary["chunks_created"] += len(chunks)
            log.info("filing_indexed", accession=filing.accession_number, chunks=len(chunks))

    log.info("indexing_done", **summary)
    return summary
