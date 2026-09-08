"""products table

Revision ID: 0003_products
Revises: 0002_notifications_audit_log
Create Date: 2026-09-08

Matches app/models/product.py exactly. Uses create_type=False on the
enum object embedded in the Column (see 0001's docstring for why this
is required — op.create_table() would otherwise try to create the
enum type a second time and fail) and values_callable is already
handled on the Python/model side (app/models/product.py), not here —
this migration only needs to define the enum's on-the-wire VALUES,
which must match what values_callable sends (the lowercase .value
strings, not the Python member names).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_products"
down_revision = "0002_notifications_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    product_status = postgresql.ENUM(
        "draft", "under_verification", "verified", "failed_verification", "suspended",
        name="product_status",
        create_type=False,
    )
    product_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("mineral_type", sa.String(100), nullable=False),
        sa.Column("grade", sa.String(100), nullable=True),
        sa.Column("specifications_notes", sa.Text(), nullable=True),
        sa.Column("quantity_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantity_unit", sa.String(20), nullable=False, server_default="MT"),
        sa.Column("price_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("price_currency", sa.String(3), nullable=False, server_default="SAR"),
        sa.Column("price_unit", sa.String(50), nullable=True),
        sa.Column("packaging", sa.String(100), nullable=True),
        sa.Column("trade_terms", sa.String(150), nullable=True),
        sa.Column("status", product_status, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_products_seller_company_id", "products", ["seller_company_id"])


def downgrade() -> None:
    op.drop_index("ix_products_seller_company_id", table_name="products")
    op.drop_table("products")
    postgresql.ENUM(name="product_status").drop(op.get_bind(), checkfirst=True)
