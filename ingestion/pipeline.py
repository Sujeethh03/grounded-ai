"""M1: end-to-end ingestion — fetch a company's filings, normalize, persist.

Deliberately not a Celery task yet: M1's goal is proving fetch -> normalize ->
persist works against real data with a synchronous, directly-callable
function. Wrapping this in `ingestion/tasks.py` for the async Celery/Redis
pipeline is later scope (see PROGRESS.md) — don't reach for the queue before
the underlying logic is proven.

Chunking + embedding (M3) and the graph loader (M4) are not wired in here;
this only gets filings into `filings` + `filing_sections`, which is the whole
M1 milestone per the dossier.
"""

from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select

from db.models import Filing, FilingSection, IngestionStatus
from db.session import get_session
from ingestion.fetch_edgar import EDGARFetchFailed, fetch_filing_document, filing_source_url, get_company_filings
from ingestion.normalize import NormalizedDocument, NormalizedSection, normalize_filing
from ingestion.ocr_fallback import extract_text_via_ocr, looks_like_pdf
from ingestion.schema_drift import check_structure

log = structlog.get_logger(__name__)


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


async def ingest_company(cik: str, limit: int = 5) -> dict[str, int]:
    """Fetch, normalize, and persist a company's most recent 10-K/10-Q/8-K filings.

    `limit` caps how many filings we pull per run — deliberately small for a
    first pass so we don't hammer EDGAR (or wait minutes) while proving the
    pipeline out; raise it once this is stable.
    """
    summary = {"fetched": 0, "skipped_existing": 0, "succeeded": 0, "failed": 0}

    async with httpx.AsyncClient(timeout=30.0) as client:
        metas = (await get_company_filings(cik, client=client))[:limit]
        summary["fetched"] = len(metas)

        for meta in metas:
            with get_session() as session:
                existing = session.scalar(select(Filing).where(Filing.accession_number == meta.accession_number))
                if existing:
                    summary["skipped_existing"] += 1
                    log.info("filing_already_ingested", accession=meta.accession_number)
                    continue

                report_date = _parse_date(meta.report_date)
                filing = Filing(
                    company_cik=meta.cik,
                    company_name=meta.company_name,
                    form_type=meta.form_type,
                    accession_number=meta.accession_number,
                    fiscal_year=report_date.year if report_date else None,
                    filing_date=_parse_date(meta.filing_date),
                    source_url=filing_source_url(meta),
                    ingestion_status=IngestionStatus.PENDING.value,
                )
                session.add(filing)
                session.flush()  # assigns filing.id for the FilingSection FK below

                try:
                    raw = await fetch_filing_document(meta, client=client)

                    if looks_like_pdf(raw):
                        # M2 OCR path: scanned/PDF-only document, no HTML to parse.
                        ocr = extract_text_via_ocr(raw)
                        doc = NormalizedDocument(
                            accession_number=meta.accession_number,
                            form_type=meta.form_type,
                            sections=[NormalizedSection(name="Full Text (OCR)", index=0, text=ocr.text)],
                        )
                        filing.ingestion_status = IngestionStatus.OCR_FALLBACK.value
                        filing.ocr_confidence = ocr.confidence
                        log.info(
                            "filing_routed_to_ocr",
                            accession=meta.accession_number,
                            confidence=ocr.confidence,
                        )
                    else:
                        doc = normalize_filing(
                            raw.decode("utf-8", errors="replace"), meta.form_type, meta.accession_number
                        )
                        drift = check_structure(doc)
                        if not drift.ok:
                            # Keep the sections for triage, but never let a bad
                            # parse flow silently into the index (M3 skips these).
                            filing.ingestion_status = IngestionStatus.SCHEMA_DRIFT_FLAGGED.value
                            log.warning(
                                "filing_schema_drift_flagged",
                                accession=meta.accession_number,
                                reason=drift.reason,
                            )

                    for section in doc.sections:
                        session.add(
                            FilingSection(
                                filing_id=filing.id,
                                section_name=section.name,
                                section_index=section.index,
                                text=section.text,
                            )
                        )
                    filing.ingested_at = datetime.now(timezone.utc)
                    summary["succeeded"] += 1
                    log.info(
                        "filing_ingested",
                        accession=meta.accession_number,
                        form_type=meta.form_type,
                        status=filing.ingestion_status,
                        sections=len(doc.sections),
                    )
                except EDGARFetchFailed as exc:
                    filing.ingestion_status = IngestionStatus.FAILED.value
                    summary["failed"] += 1
                    log.error("filing_ingest_failed", accession=meta.accession_number, error=str(exc))

    log.info("ingest_company_done", cik=cik, **summary)
    return summary
