"""rfqs table

Revision ID: 0008_rfqs
Revises: 0007_lockout_2fa
Create Date: 2026-09-10

Matches app/models/rfq.py. Standing rule applies: create_type=False on
the enum object embedded in the Column (see 0001's docstring).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0008_rfqs"
down_revision = "0007_lockout_2fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    rfq_status = postgresql.ENUM("open", "closed", name="rfq_status", create_type=False)
    rfq_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "rfqs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("buyer_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("mineral_type", sa.String(100), nullable=False),
        sa.Column("specifications_notes", sa.Text(), nullable=True),
        sa.Column("quantity_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantity_unit", sa.String(20), nullable=False, server_default="MT"),
        sa.Column("delivery_location", sa.String(150), nullable=False),
        sa.Column("delivery_timeframe", sa.String(100), nullable=False),
        sa.Column("commercial_terms_notes", sa.Text(), nullable=True),
        sa.Column("status", rfq_status, nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rfqs_buyer_company_id", "rfqs", ["buyer_company_id"])


def downgrade() -> None:
    op.drop_index("ix_rfqs_buyer_company_id", table_name="rfqs")
    op.drop_table("rfqs")
    postgresql.ENUM(name="rfq_status").drop(op.get_bind(), checkfirst=True)
