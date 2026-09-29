"""monitoring

Revision ID: 0023_monitoring
Revises: 0022_company_documents
Create Date: 2026-09-29 12:38:17.199959

"""
from alembic import op
import sqlalchemy as sa


revision = '0023_monitoring'
down_revision = '0022_company_documents'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('request_stats',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('bucket', sa.DateTime(timezone=True), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('route', sa.String(length=200), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('errors_4xx', sa.Integer(), nullable=False),
    sa.Column('errors_5xx', sa.Integer(), nullable=False),
    sa.Column('total_ms', sa.BigInteger(), nullable=False),
    sa.Column('max_ms', sa.Integer(), nullable=False),
    sa.Column('slow', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('request_stats_pkey')),
    sa.UniqueConstraint('bucket', 'method', 'route', name='uq_request_stats_bucket_route')
    )
    op.create_index(op.f('ix_request_stats_bucket'), 'request_stats', ['bucket'], unique=False)
    op.create_table('error_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=True),
    sa.Column('path', sa.String(length=500), nullable=True),
    sa.Column('route', sa.String(length=200), nullable=True),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('error_type', sa.String(length=200), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('traceback', sa.Text(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('error_events_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('error_events_pkey'))
    )
    op.create_index('ix_error_events_occurred_at', 'error_events', ['occurred_at'], unique=False)
    op.create_table('job_runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('job', sa.String(length=50), nullable=False),
    sa.Column('trigger', sa.String(length=20), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('items', sa.Integer(), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('triggered_by_user_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], name=op.f('job_runs_triggered_by_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('job_runs_pkey'))
    )
    op.create_index('ix_job_runs_job_started', 'job_runs', ['job', 'started_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_job_runs_job_started', table_name='job_runs')
    op.drop_table('job_runs')
    op.drop_index('ix_error_events_occurred_at', table_name='error_events')
    op.drop_table('error_events')
    op.drop_index(op.f('ix_request_stats_bucket'), table_name='request_stats')
    op.drop_table('request_stats')
