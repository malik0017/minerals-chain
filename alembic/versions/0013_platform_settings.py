"""platform settings: admin toggles for per-role registration + email OTP requirement

Revision ID: 0013_platform_settings
Revises: 0012_registration_docs
Create Date: 2026-09-21

Task #4: a single-row settings table (see app/models/platform_settings.py
docstring for why it's one row rather than a key/value table). Seeds that
one row with every field at its existing, safe default so behavior is
identical to before this migration until an admin visits the new
/admin/settings page and changes something.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0013_platform_settings"
down_revision = "0012_registration_docs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("registration_enabled_seller", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("registration_enabled_buyer", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("registration_enabled_lab", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_email_otp", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        "INSERT INTO platform_settings (id, registration_enabled_seller, registration_enabled_buyer, "
        "registration_enabled_lab, require_email_otp) VALUES (1, true, true, true, true)"
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
