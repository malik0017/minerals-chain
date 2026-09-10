"""orders table

Revision ID: 0010_orders
Revises: 0009_quotations
Create Date: 2026-09-10

Matches app/models/order.py. Standing rule applies: create_type=False
on the enum object embedded in the Column (see 0001's docstring).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0010_orders"
down_revision = "0009_quotations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    order_status = postgresql.ENUM(
        "pending_confirmation", "confirmed", "in_transit", "delivered", "completed",
        name="order_status",
        create_type=False,
    )
    order_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rfqs.id"), nullable=False),
        sa.Column(
            "quotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quotations.id"),
            nullable=False, unique=True,
        ),
        sa.Column("buyer_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("seller_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("status", order_status, nullable=False, server_default="pending_confirmation"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_buyer_company_id", "orders", ["buyer_company_id"])
    op.create_index("ix_orders_seller_company_id", "orders", ["seller_company_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_seller_company_id", table_name="orders")
    op.drop_index("ix_orders_buyer_company_id", table_name="orders")
    op.drop_table("orders")
    postgresql.ENUM(name="order_status").drop(op.get_bind(), checkfirst=True)
