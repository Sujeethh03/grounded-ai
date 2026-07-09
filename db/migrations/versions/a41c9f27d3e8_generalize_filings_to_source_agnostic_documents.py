"""Generalize filings -> source-agnostic documents (GroundedAI multi-source pivot)

The platform now ingests more than SEC filings (first new source: openFDA drug
labels), so the document tables lose their SEC-specific names:

    filings          -> documents        filing_sections -> document_sections
    company_cik      -> entity_id        (cik for SEC; generic drug name for labels)
    company_name     -> entity_name
    form_type        -> doc_type
    fiscal_year      -> year
    accession_number -> source_key       (accession for SEC; openFDA set_id for labels)
    filing_date      -> published_at

Plus two new columns: source_type ('sec_filing' | 'drug_label') and meta JSONB
for source-specific fields that don't deserve their own column (label version,
brand/generic name lists, manufacturer, ...). Existing rows are all SEC.

Revision ID: a41c9f27d3e8
Revises: 0276fbec8f45
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a41c9f27d3e8'
down_revision: Union[str, Sequence[str], None] = '0276fbec8f45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('filings', 'documents')
    op.rename_table('filing_sections', 'document_sections')

    # documents: column renames (indexes/constraints follow the column in PG)
    op.alter_column('documents', 'company_cik', new_column_name='entity_id')
    op.alter_column('documents', 'company_name', new_column_name='entity_name')
    op.alter_column('documents', 'form_type', new_column_name='doc_type')
    op.alter_column('documents', 'fiscal_year', new_column_name='year')
    op.alter_column('documents', 'accession_number', new_column_name='source_key')
    op.alter_column('documents', 'filing_date', new_column_name='published_at')

    # entity_id and source_key must fit non-SEC identifiers (generic drug
    # names / 36-char openFDA set_ids), so widen both.
    op.alter_column('documents', 'entity_id', type_=sa.String(64))
    op.alter_column('documents', 'source_key', type_=sa.String(64))

    op.add_column(
        'documents',
        sa.Column('source_type', sa.String(16), nullable=False, server_default='sec_filing'),
    )
    op.alter_column('documents', 'source_type', server_default=None)
    op.add_column('documents', sa.Column('meta', postgresql.JSONB(), nullable=True))
    op.create_index('ix_documents_source_type', 'documents', ['source_type'])

    # FK column renames
    op.alter_column('document_sections', 'filing_id', new_column_name='document_id')
    op.alter_column('doc_chunks', 'filing_id', new_column_name='document_id')

    # Cosmetic-but-important hygiene: constraint/index names should not lie
    # about which table they belong to.
    op.execute('ALTER TABLE documents RENAME CONSTRAINT uq_filings_accession_number TO uq_documents_source_key')
    op.execute('ALTER TABLE documents RENAME CONSTRAINT ck_filings_ingestion_status TO ck_documents_ingestion_status')
    op.execute('ALTER INDEX IF EXISTS ix_filings_company_cik RENAME TO ix_documents_entity_id')
    op.execute('ALTER INDEX IF EXISTS ix_filing_sections_filing_id RENAME TO ix_document_sections_document_id')
    op.execute('ALTER INDEX IF EXISTS ix_doc_chunks_filing_id RENAME TO ix_doc_chunks_document_id')
    op.execute('ALTER TABLE documents RENAME CONSTRAINT filings_pkey TO documents_pkey')
    op.execute('ALTER TABLE document_sections RENAME CONSTRAINT filing_sections_pkey TO document_sections_pkey')
    op.execute(
        'ALTER TABLE document_sections RENAME CONSTRAINT filing_sections_filing_id_fkey '
        'TO document_sections_document_id_fkey'
    )
    op.execute(
        'ALTER TABLE doc_chunks RENAME CONSTRAINT doc_chunks_filing_id_fkey TO doc_chunks_document_id_fkey'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('ALTER TABLE doc_chunks RENAME CONSTRAINT doc_chunks_document_id_fkey TO doc_chunks_filing_id_fkey')
    op.execute(
        'ALTER TABLE document_sections RENAME CONSTRAINT document_sections_document_id_fkey '
        'TO filing_sections_filing_id_fkey'
    )
    op.execute('ALTER TABLE document_sections RENAME CONSTRAINT document_sections_pkey TO filing_sections_pkey')
    op.execute('ALTER TABLE documents RENAME CONSTRAINT documents_pkey TO filings_pkey')
    op.execute('ALTER INDEX IF EXISTS ix_doc_chunks_document_id RENAME TO ix_doc_chunks_filing_id')
    op.execute('ALTER INDEX IF EXISTS ix_document_sections_document_id RENAME TO ix_filing_sections_filing_id')
    op.execute('ALTER INDEX IF EXISTS ix_documents_entity_id RENAME TO ix_filings_company_cik')
    op.execute('ALTER TABLE documents RENAME CONSTRAINT ck_documents_ingestion_status TO ck_filings_ingestion_status')
    op.execute('ALTER TABLE documents RENAME CONSTRAINT uq_documents_source_key TO uq_filings_accession_number')

    op.alter_column('doc_chunks', 'document_id', new_column_name='filing_id')
    op.alter_column('document_sections', 'document_id', new_column_name='filing_id')

    op.drop_index('ix_documents_source_type', table_name='documents')
    op.drop_column('documents', 'meta')
    op.drop_column('documents', 'source_type')

    op.alter_column('documents', 'source_key', type_=sa.String(32))
    op.alter_column('documents', 'entity_id', type_=sa.String(10))
    op.alter_column('documents', 'published_at', new_column_name='filing_date')
    op.alter_column('documents', 'source_key', new_column_name='accession_number')
    op.alter_column('documents', 'year', new_column_name='fiscal_year')
    op.alter_column('documents', 'doc_type', new_column_name='form_type')
    op.alter_column('documents', 'entity_name', new_column_name='company_name')
    op.alter_column('documents', 'entity_id', new_column_name='company_cik')

    op.rename_table('document_sections', 'filing_sections')
    op.rename_table('documents', 'filings')
