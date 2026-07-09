"""M3: chunk + embed ingested documents into doc_chunks.

Only 'pending' and 'ocr_fallback' documents get indexed — 'schema_drift_flagged'
is deliberately excluded (a bad parse in the index poisons retrieval quality
invisibly; that's the whole reason the flag exists). OCR'd documents ARE indexed
but carry document.ocr_confidence down onto every chunk so retrieval/synthesis
can discount low-quality text.

Source-blind by design: SEC filings and drug labels arrive here as identical
Document/DocumentSection rows, so one indexer serves every source.
"""

import structlog
from sqlalchemy import select

from db.models import DocChunk, Document, DocumentSection, IngestionStatus
from db.session import get_session
from retrieval.chunking import chunk_section
from retrieval.embeddings import Embedder

log = structlog.get_logger(__name__)

INDEXABLE_STATUSES = (IngestionStatus.PENDING.value, IngestionStatus.OCR_FALLBACK.value)


def index_pending_documents(embedder: Embedder) -> dict[str, int]:
    summary = {"documents_indexed": 0, "chunks_created": 0, "skipped_flagged": 0}

    with get_session() as session:
        flagged = session.scalars(
            select(Document).where(Document.ingestion_status == IngestionStatus.SCHEMA_DRIFT_FLAGGED.value)
        ).all()
        summary["skipped_flagged"] = len(flagged)

        documents = session.scalars(
            select(Document).where(Document.ingestion_status.in_(INDEXABLE_STATUSES))
        ).all()

        for document in documents:
            sections = session.scalars(
                select(DocumentSection)
                .where(DocumentSection.document_id == document.id)
                .order_by(DocumentSection.section_index)
            ).all()

            chunks = []
            for section in sections:
                chunks.extend(chunk_section(section.section_name, section.text, start_index=len(chunks)))
            if not chunks:
                log.warning("document_produced_no_chunks", source_key=document.source_key)
                continue

            vectors = embedder.embed([c.text for c in chunks])
            for chunk, vector in zip(chunks, vectors):
                session.add(
                    DocChunk(
                        document_id=document.id,
                        section=chunk.section_name,
                        chunk_index=chunk.chunk_index,
                        chunk_text=chunk.text,
                        embedding=vector,
                        ocr_confidence=document.ocr_confidence,
                    )
                )
            document.ingestion_status = IngestionStatus.INDEXED.value
            summary["documents_indexed"] += 1
            summary["chunks_created"] += len(chunks)
            log.info("document_indexed", source_key=document.source_key, chunks=len(chunks))

    log.info("indexing_done", **summary)
    return summary
