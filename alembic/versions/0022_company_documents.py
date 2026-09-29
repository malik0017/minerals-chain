"""company_documents

Revision ID: 0022_company_documents
Revises: 0021_shipments
Create Date: 2026-09-29 12:30:55.054511

"""
from alembic import op
import sqlalchemy as sa

BACKFILL = """
INSERT INTO company_documents (id, company_id, doc_type, number, expires_on, version, is_current, status,
                               file_path, original_name, created_at, updated_at, reviewed_at)
SELECT gen_random_uuid(), c.id, d.doc_type, d.number, d.expires_on, 1, true,
       CASE WHEN c.status = 'approved' THEN 'approved' WHEN c.status = 'rejected' THEN 'rejected' ELSE 'pending' END,
       'company_documents/' || d.filename, d.filename, c.created_at, c.created_at,
       CASE WHEN c.status = 'approved' THEN c.updated_at END
FROM companies c
CROSS JOIN LATERAL (VALUES ('cr', c.cr_number, NULL::date, c.cr_document_filename),
                           ('license', c.license_or_accreditation_number, c.license_valid_until, c.license_document_filename)
                   ) AS d(doc_type, number, expires_on, filename)
WHERE d.filename IS NOT NULL AND d.filename <> ''
"""


revision = '0022_company_documents'
down_revision = '0021_shipments'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('company_documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('doc_type', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('number', sa.String(length=80), nullable=True),
    sa.Column('issued_on', sa.Date(), nullable=True),
    sa.Column('expires_on', sa.Date(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('reviewed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('file_path', sa.String(length=255), nullable=False),
    sa.Column('file_sha256', sa.String(length=64), nullable=True),
    sa.Column('file_size', sa.BigInteger(), nullable=True),
    sa.Column('mime', sa.String(length=80), nullable=True),
    sa.Column('original_name', sa.String(length=255), nullable=True),
    sa.Column('last_reminder_days', sa.Integer(), nullable=True),
    sa.Column('uploaded_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('company_documents_company_id_fkey')),
    sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], name=op.f('company_documents_reviewed_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], name=op.f('company_documents_uploaded_by_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('company_documents_pkey'))
    )
    op.create_index(op.f('ix_company_documents_company_id'), 'company_documents', ['company_id'], unique=False)
    op.create_index('ix_company_documents_company_type', 'company_documents', ['company_id', 'doc_type'], unique=False)
    op.create_index(op.f('ix_company_documents_expires_on'), 'company_documents', ['expires_on'], unique=False)
    op.execute(BACKFILL)


def downgrade() -> None:
    op.drop_index(op.f('ix_company_documents_expires_on'), table_name='company_documents')
    op.drop_index('ix_company_documents_company_type', table_name='company_documents')
    op.drop_index(op.f('ix_company_documents_company_id'), table_name='company_documents')
    op.drop_table('company_documents')
