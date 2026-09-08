"""verification_requests and certificates tables

Revision ID: 0004_verification
Revises: 0003_products
Create Date: 2026-09-08

Matches app/models/verification.py and app/models/certificate.py.
create_type=False on the enum embedded in the Column, per the standing
rule (see 0001's docstring) — required every time a migration both
creates a Postgres enum type and uses it in the same op.create_table().
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_verification"
down_revision = "0003_products"
branch_labels = None
depends_on = None


def upgrade() -> None:
    verification_status = postgresql.ENUM(
        "requested", "sample_scheduled", "testing_in_progress", "completed", "failed",
        name="verification_status",
        create_type=False,
    )
    verification_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "verification_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("lab_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("status", verification_status, nullable=False, server_default="requested"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_requests_product_id", "verification_requests", ["product_id"])
    op.create_index("ix_verification_requests_lab_company_id", "verification_requests", ["lab_company_id"])

    op.create_table(
        "certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "verification_request_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("verification_requests.id"), nullable=False, unique=True,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("lab_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("certificate_number", sa.String(30), nullable=False, unique=True),
        sa.Column("tested_parameters_notes", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("certificates")
    op.drop_index("ix_verification_requests_lab_company_id", table_name="verification_requests")
    op.drop_index("ix_verification_requests_product_id", table_name="verification_requests")
    op.drop_table("verification_requests")
    postgresql.ENUM(name="verification_status").drop(op.get_bind(), checkfirst=True)
