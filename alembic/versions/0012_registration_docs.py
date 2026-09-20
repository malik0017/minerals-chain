"""registration overhaul: license mandatory for all roles, CR/license document filenames

Revision ID: 0012_registration_docs
Revises: 0011_schema_evolution
Create Date: 2026-09-17

Pre-production, no real data — confirmed safe for a straightforward
ALTER (no data backfill needed for the new NOT NULL columns).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012_registration_docs"
down_revision = "0011_schema_evolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("companies", "license_or_accreditation_number", nullable=False)
    op.add_column("companies", sa.Column("cr_document_filename", sa.String(255), nullable=False, server_default=""))
    op.add_column("companies", sa.Column("license_document_filename", sa.String(255), nullable=False, server_default=""))
    # Drop the server_default once existing rows (none, pre-production) are backfilled —
    # it exists only so the ADD COLUMN...NOT NULL succeeds; new inserts always provide
    # a real filename via the application layer (see Company model docstring).
    op.alter_column("companies", "cr_document_filename", server_default=None)
    op.alter_column("companies", "license_document_filename", server_default=None)


def downgrade() -> None:
    op.drop_column("companies", "license_document_filename")
    op.drop_column("companies", "cr_document_filename")
    op.alter_column("companies", "license_or_accreditation_number", nullable=True)
