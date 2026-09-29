"""shipments

Revision ID: 0021_shipments
Revises: 0020_erp_export
Create Date: 2026-09-29 12:26:11.297634

"""
from alembic import op
import sqlalchemy as sa


revision = '0021_shipments'
down_revision = '0020_erp_export'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('shipments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('reference', sa.String(length=30), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('seller_company_id', sa.UUID(), nullable=False),
    sa.Column('buyer_company_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('transport_mode', sa.String(length=20), nullable=False),
    sa.Column('carrier_name', sa.String(length=150), nullable=True),
    sa.Column('tracking_number', sa.String(length=80), nullable=True),
    sa.Column('vehicle_plate', sa.String(length=30), nullable=True),
    sa.Column('driver_name', sa.String(length=120), nullable=True),
    sa.Column('driver_phone', sa.String(length=30), nullable=True),
    sa.Column('origin', sa.String(length=150), nullable=True),
    sa.Column('destination', sa.String(length=150), nullable=True),
    sa.Column('weighbridge_ticket', sa.String(length=60), nullable=True),
    sa.Column('gross_weight_t', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('tare_weight_t', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('received_net_t', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('eta', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['buyer_company_id'], ['companies.id'], name=op.f('shipments_buyer_company_id_fkey')),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('shipments_created_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('shipments_order_id_fkey')),
    sa.ForeignKeyConstraint(['seller_company_id'], ['companies.id'], name=op.f('shipments_seller_company_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('shipments_pkey')),
    sa.UniqueConstraint('reference', name=op.f('shipments_reference_key'))
    )
    op.create_index(op.f('ix_shipments_buyer_company_id'), 'shipments', ['buyer_company_id'], unique=False)
    op.create_index(op.f('ix_shipments_order_id'), 'shipments', ['order_id'], unique=False)
    op.create_index(op.f('ix_shipments_seller_company_id'), 'shipments', ['seller_company_id'], unique=False)
    op.create_table('shipment_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('shipment_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('location', sa.String(length=150), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('shipment_events_created_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], name=op.f('shipment_events_shipment_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('shipment_events_pkey'))
    )
    op.create_index(op.f('ix_shipment_events_shipment_id'), 'shipment_events', ['shipment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_shipment_events_shipment_id'), table_name='shipment_events')
    op.drop_table('shipment_events')
    op.drop_index(op.f('ix_shipments_seller_company_id'), table_name='shipments')
    op.drop_index(op.f('ix_shipments_order_id'), table_name='shipments')
    op.drop_index(op.f('ix_shipments_buyer_company_id'), table_name='shipments')
    op.drop_table('shipments')
