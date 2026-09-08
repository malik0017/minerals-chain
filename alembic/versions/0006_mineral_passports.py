"""mineral_passports table

Revision ID: 0006_mineral_passports
Revises: 0005_user_avatar
Create Date: 2026-09-08

Matches app/models/passport.py. Standing rule applies: create_type=False
on the enum objects embedded in the Column (see 0001's docstring).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0006_mineral_passports"
down_revision = "0005_user_avatar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    passport_scope = postgresql.ENUM(
        "domestic", "gcc_export", "international_export",
        name="passport_scope",
        create_type=False,
    )
    passport_status = postgresql.ENUM(
        "pending", "approved", "rejected",
        name="passport_status",
        create_type=False,
    )
    bind = op.get_bind()
    passport_scope.create(bind, checkfirst=True)
    passport_status.create(bind, checkfirst=True)

    op.create_table(
        "mineral_passports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("seller_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("scope", passport_scope, nullable=False),
        sa.Column("status", passport_status, nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("passport_number", sa.String(30), nullable=True, unique=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mineral_passports_product_id", "mineral_passports", ["product_id"])
    op.create_index("ix_mineral_passports_seller_company_id", "mineral_passports", ["seller_company_id"])


def downgrade() -> None:
    op.drop_index("ix_mineral_passports_seller_company_id", table_name="mineral_passports")
    op.drop_index("ix_mineral_passports_product_id", table_name="mineral_passports")
    op.drop_table("mineral_passports")
    postgresql.ENUM(name="passport_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="passport_scope").drop(op.get_bind(), checkfirst=True)
