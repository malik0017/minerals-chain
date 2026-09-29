"""system settings: admin-editable runtime configuration

Revision ID: 0016_system_settings
Revises: 0015_schema_v1_alignment
Create Date: 2026-09-28

Batch K — Admin Control Center: typed key/value runtime settings (fees, VAT,
validity periods, numbering prefixes, security thresholds, dev tools). Only
changed values are stored; definitions + defaults live in
app/core/system_settings.py. See app/models/system_setting.py for why this
supersedes growing the single-row platform_settings table (which is kept).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # noqa: F401

# revision identifiers, used by Alembic.
revision = "0016_system_settings"
down_revision = "0015_schema_v1_alignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('system_settings',
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], name=op.f('system_settings_updated_by_user_id_fkey')),
    sa.PrimaryKeyConstraint('key', name=op.f('system_settings_pkey'))
    )


def downgrade() -> None:
    op.drop_table('system_settings')
