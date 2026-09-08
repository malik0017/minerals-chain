"""add avatar_filename to users

Revision ID: 0005_user_avatar
Revises: 0004_verification
Create Date: 2026-09-08

Simple additive column, nullable, no enum involved — none of the
create_type=False gotchas from earlier migrations apply here.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_user_avatar"
down_revision = "0004_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_filename", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_filename")
