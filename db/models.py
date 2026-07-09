"""SQLAlchemy models for GroundedAI.

Originally mirrored the Portfolio Dossier's SEC-specific schema (filings /
filing_sections); generalized in migration a41c9f27d3e8 when the platform
gained its second document source (openFDA drug labels). The recorded
deviation from the dossier: table and column names are now source-agnostic
(`documents.entity_name`, not `filings.company_name`) with a `source_type`
discriminator and a `meta` JSONB column for source-specific fields — one
pipeline, N document sources, no parallel table hierarchies.

`DocumentSection` holds the normalized Document -> Section output of
ingestion, ahead of chunking/embedding (`DocChunk`).
"""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    OCR_FALLBACK = "ocr_fallback"
    SCHEMA_DRIFT_FLAGGED = "schema_drift_flagged"
    INDEXED = "indexed"
    FAILED = "failed"


class SourceType(str, enum.Enum):
    SEC_FILING = "sec_filing"
    DRUG_LABEL = "drug_label"


class Document(Base):
    """One ingested source document, from any source.

    Field semantics per source:
        source_type   'sec_filing'                'drug_label'
        entity_id     zero-padded CIK             lowercase generic drug name
        entity_name   company name                brand name (or generic if unbranded)
        doc_type      '10-K' / '10-Q' / '8-K'     'drug_label'
        source_key    accession number            openFDA set_id
        year          fiscal year                 label effective year
        meta          (unused)                    {version, brand_names, generic_names,
                                                   manufacturer, product_type}
    """

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_documents_source_key"),
        CheckConstraint(
            "ingestion_status in ('pending','ocr_fallback','schema_drift_flagged','indexed','failed')",
            name="ck_documents_ingestion_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(16), default=SourceType.SEC_FILING.value, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_name: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(16))
    year: Mapped[int | None] = mapped_column(nullable=True)
    source_key: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    ingestion_status: Mapped[str] = mapped_column(String(32), default=IngestionStatus.PENDING.value)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Mean Tesseract word confidence (0-1) when the OCR path ran; NULL for text-native documents.
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    sections: Mapped[list["DocumentSection"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentSection(Base):
    """One row per normalized section of a document (e.g. 'Item 1A. Risk Factors'
    for a 10-K, 'Drug Interactions' for a drug label)."""

    __tablename__ = "document_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    section_name: Mapped[str] = mapped_column(String(255))
    section_index: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)

    document: Mapped["Document"] = relationship(back_populates="sections")


class DocChunk(Base):
    """Chunk + embedding + lexical tsvector — one table serves both halves
    of hybrid search (the reason we chose pgvector over a separate vector DB).
    """

    __tablename__ = "doc_chunks"
    __table_args__ = (
        Index("ix_doc_chunks_text_tsv", "text_tsv", postgresql_using="gin"),
        Index(
            "ix_doc_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    section: Mapped[str] = mapped_column(String(255))
    chunk_index: Mapped[int] = mapped_column(default=0)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    text_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', chunk_text)", persisted=True), nullable=True
    )
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class GoldenQA(Base):
    """Eval harness fixtures."""

    __tablename__ = "golden_qa"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str] = mapped_column(Text)
    requires_graph: Mapped[bool] = mapped_column(default=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")
