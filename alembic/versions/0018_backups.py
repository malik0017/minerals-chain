"""backup runs

Revision ID: 0018_backups
Revises: 0017_brd_completion
Create Date: 2026-09-29 12:11:07.144922

"""
from alembic import op
import sqlalchemy as sa


revision = '0018_backups'
down_revision = '0017_brd_completion'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('backup_runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=True),
    sa.Column('db_sha256', sa.String(length=64), nullable=True),
    sa.Column('files_count', sa.BigInteger(), nullable=True),
    sa.Column('alembic_revision', sa.String(length=64), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('trigger', sa.String(length=20), nullable=False),
    sa.Column('triggered_by_user_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], name=op.f('backup_runs_triggered_by_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('backup_runs_pkey'))
    )
    op.drop_constraint(op.f('users_email_key'), 'users', type_='unique')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_unique_constraint(op.f('users_email_key'), 'users', ['email'], postgresql_nulls_not_distinct=False)
    op.drop_table('backup_runs')
