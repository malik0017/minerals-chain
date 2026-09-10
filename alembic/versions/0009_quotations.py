"""quotations table

Revision ID: 0009_quotations
Revises: 0008_rfqs
Create Date: 2026-09-10

Matches app/models/quotation.py. Standing rule applies: create_type=False
on the enum object embedded in the Column (see 0001's docstring).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0009_quotations"
down_revision = "0008_rfqs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    quotation_status = postgresql.ENUM("submitted", "accepted", name="quotation_status", create_type=False)
    quotation_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "quotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rfqs.id"), nullable=False),
        sa.Column("seller_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("price_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("price_currency", sa.String(3), nullable=False, server_default="SAR"),
        sa.Column("price_unit", sa.String(30), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("terms_notes", sa.Text(), nullable=True),
        sa.Column("status", quotation_status, nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quotations_rfq_id", "quotations", ["rfq_id"])
    op.create_index("ix_quotations_seller_company_id", "quotations", ["seller_company_id"])


def downgrade() -> None:
    op.drop_index("ix_quotations_seller_company_id", table_name="quotations")
    op.drop_index("ix_quotations_rfq_id", table_name="quotations")
    op.drop_table("quotations")
    postgresql.ENUM(name="quotation_status").drop(op.get_bind(), checkfirst=True)
