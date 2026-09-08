"""initial: companies and users tables

Revision ID: 0001_initial_company_user
Revises:
Create Date: 2026-09-08

Hand-written to match app/models/company.py and app/models/user.py
exactly (Batch 1). From Batch 2 onward, prefer generating migrations
with `alembic revision --autogenerate -m "..."` and just reviewing the
output — do it by hand only if autogenerate misses something.

BUGFIX (post-Batch-3): the four ENUM(...) objects below now pass
create_type=False. Without it, this migration fails every single time
with "type ... already exists": the explicit .create(checkfirst=True)
calls create the type, then op.create_table() ALSO tries to create the
same type as part of the table's own DDL (Alembic always calls that
with checkfirst=False), colliding with the type we just created two
lines above, inside the same transaction. create_type=False tells
SQLAlchemy "don't manage this type's lifecycle via table create/drop
events" — we're already doing that ourselves via the explicit
.create()/.drop() calls, which is the standard fix for this exact
scenario.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_company_user"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    company_role = postgresql.ENUM("seller", "buyer", "lab", name="company_role", create_type=False)
    approval_status = postgresql.ENUM(
        "pending", "approved", "rejected", "suspended", name="approval_status", create_type=False
    )
    subscription_tier = postgresql.ENUM("entry", "mid", "premium", name="subscription_tier", create_type=False)
    user_role = postgresql.ENUM("seller", "buyer", "lab", "admin", name="user_role", create_type=False)

    bind = op.get_bind()
    company_role.create(bind, checkfirst=True)
    approval_status.create(bind, checkfirst=True)
    subscription_tier.create(bind, checkfirst=True)
    user_role.create(bind, checkfirst=True)

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("role", company_role, nullable=False),
        sa.Column("cr_number", sa.String(50), nullable=False, unique=True),
        sa.Column("license_or_accreditation_number", sa.String(100), nullable=True),
        sa.Column("status", approval_status, nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subscription_tier", subscription_tier, nullable=True, server_default="entry"),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column("contact_phone", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("preferred_language", sa.String(2), nullable=False, server_default="en"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # companies.reviewed_by_user_id -> users.id (added after users exists to avoid a circular create order)
    op.create_foreign_key(
        "fk_companies_reviewed_by_user_id",
        "companies",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_companies_reviewed_by_user_id", "companies", type_="foreignkey")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("companies")

    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="subscription_tier").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="approval_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="company_role").drop(op.get_bind(), checkfirst=True)
