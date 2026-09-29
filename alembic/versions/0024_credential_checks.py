"""credential checks

Revision ID: 0024_credential_checks
Revises: 0023_monitoring
Create Date: 2026-09-29 12:42:45.465244

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0024_credential_checks'
down_revision = '0023_monitoring'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('credential_checks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.Column('reference_number', sa.String(length=60), nullable=False),
    sa.Column('result', sa.String(length=20), nullable=False),
    sa.Column('name_on_record', sa.String(length=255), nullable=True),
    sa.Column('status_on_record', sa.String(length=60), nullable=True),
    sa.Column('issued_on', sa.Date(), nullable=True),
    sa.Column('expires_on', sa.Date(), nullable=True),
    sa.Column('name_match', sa.Boolean(), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('checked_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['checked_by_user_id'], ['users.id'], name=op.f('credential_checks_checked_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('credential_checks_company_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('credential_checks_pkey'))
    )
    op.create_index(op.f('ix_credential_checks_company_id'), 'credential_checks', ['company_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_credential_checks_company_id'), table_name='credential_checks')
    op.drop_table('credential_checks')
