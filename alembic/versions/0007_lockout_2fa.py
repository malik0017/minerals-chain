"""add lockout and 2FA columns to users

Revision ID: 0007_lockout_2fa
Revises: 0006_mineral_passports
Create Date: 2026-09-09

All additive columns, nullable or with sensible defaults — no enum
types involved, none of the create_type=False gotchas apply here.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_lockout_2fa"
down_revision = "0006_mineral_passports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("totp_secret", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
