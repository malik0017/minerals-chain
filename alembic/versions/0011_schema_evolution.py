"""schema evolution: VAT registration number, subscriptions table,
Certification/CertificationScope replacing certificates/mineral_passports

Revision ID: 0011_schema_evolution
Revises: 0010_orders
Create Date: 2026-09-17

Pre-production, no real data to preserve — confirmed with the
business owner before writing this migration. certificates and
mineral_passports are dropped outright rather than data-migrated; if
this is ever run against a database with real rows in those tables,
STOP and write a data-preserving migration instead.

Standing rule applies throughout: create_type=False on every enum
object embedded in a Column (see 0001's docstring).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0011_schema_evolution"
down_revision = "0010_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Company: VAT Registration Number ---
    op.add_column("companies", sa.Column("vat_registration_number", sa.String(30), nullable=True))

    # --- 2. Subscriptions (real history table; Company.subscription_tier stays as a cache) ---
    subscription_status = postgresql.ENUM(
        "active", "expired", "cancelled", name="subscription_status", create_type=False
    )
    subscription_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        # Reuses the EXISTING subscription_tier enum type (already created by 0001 for
        # companies.subscription_tier) — do NOT re-create it here, that would collide.
        sa.Column(
            "tier",
            postgresql.ENUM("entry", "mid", "premium", name="subscription_tier", create_type=False),
            nullable=False,
        ),
        sa.Column("subtype", sa.String(30), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", subscription_status, nullable=False, server_default="active"),
        sa.Column("attributes", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subscriptions_company_id", "subscriptions", ["company_id"])

    # --- 3. Drop the old narrow certificate/passport tables ---
    op.drop_table("certificates")
    op.drop_table("mineral_passports")
    postgresql.ENUM(name="passport_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="passport_scope").drop(op.get_bind(), checkfirst=True)

    # --- 4. Certifications (master) + CertificationScope (detail) ---
    certification_type = postgresql.ENUM(
        "lab_certificate", "mineral_passport", name="certification_type", create_type=False
    )
    certification_type.create(op.get_bind(), checkfirst=True)
    certification_status = postgresql.ENUM(
        "pending", "approved", "rejected", name="certification_status", create_type=False
    )
    certification_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "certifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cert_type", certification_type, nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("subject_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("issuing_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column(
            "verification_request_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("verification_requests.id"), nullable=True, unique=True,
        ),
        sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("certificate_number", sa.String(30), nullable=True, unique=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("status", certification_status, nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_certifications_subject_company_id", "certifications", ["subject_company_id"])

    op.create_table(
        "certification_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "certification_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certifications.id"), nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("attribute_name", sa.String(80), nullable=True),
        sa.Column("attribute_min", sa.Numeric(10, 3), nullable=True),
        sa.Column("attribute_max", sa.Numeric(10, 3), nullable=True),
        sa.Column("geo_region", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_certification_scopes_certification_id", "certification_scopes", ["certification_id"])


def downgrade() -> None:
    op.drop_index("ix_certification_scopes_certification_id", table_name="certification_scopes")
    op.drop_table("certification_scopes")
    op.drop_index("ix_certifications_subject_company_id", table_name="certifications")
    op.drop_table("certifications")
    postgresql.ENUM(name="certification_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="certification_type").drop(op.get_bind(), checkfirst=True)

    # Recreate the old tables on downgrade (schema only — no data, matches upgrade's
    # drop-outright approach)
    passport_scope = postgresql.ENUM(
        "domestic", "gcc_export", "international_export", name="passport_scope", create_type=False
    )
    passport_scope.create(op.get_bind(), checkfirst=True)
    passport_status = postgresql.ENUM("pending", "approved", "rejected", name="passport_status", create_type=False)
    passport_status.create(op.get_bind(), checkfirst=True)
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

    op.drop_index("ix_subscriptions_company_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    postgresql.ENUM(name="subscription_status").drop(op.get_bind(), checkfirst=True)

    op.drop_column("companies", "vat_registration_number")
