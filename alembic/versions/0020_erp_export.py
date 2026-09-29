"""erp export runs

Revision ID: 0020_erp_export
Revises: 0019_inventory
Create Date: 2026-09-29 12:20:43.581838

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0020_erp_export'
down_revision = '0019_inventory'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('erp_export_runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('target', sa.String(length=20), nullable=False),
    sa.Column('scope_company_id', sa.UUID(), nullable=True),
    sa.Column('datasets', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=True),
    sa.Column('period_end', sa.Date(), nullable=True),
    sa.Column('row_counts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('file_path', sa.String(length=255), nullable=True),
    sa.Column('file_sha256', sa.String(length=64), nullable=True),
    sa.Column('file_size', sa.BigInteger(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('erp_export_runs_created_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['scope_company_id'], ['companies.id'], name=op.f('erp_export_runs_scope_company_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('erp_export_runs_pkey'))
    )


def downgrade() -> None:
    op.drop_table('erp_export_runs')
