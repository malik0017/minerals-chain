"""inventory ledger

Revision ID: 0019_inventory
Revises: 0018_backups
Create Date: 2026-09-29 12:16:11.378392

"""
from alembic import op
import sqlalchemy as sa


revision = '0019_inventory'
down_revision = '0018_backups'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('inventory_movements',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('reference', sa.String(length=30), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('warehouse_id', sa.UUID(), nullable=True),
    sa.Column('product_id', sa.UUID(), nullable=True),
    sa.Column('product_master_id', sa.UUID(), nullable=True),
    sa.Column('batch_id', sa.UUID(), nullable=True),
    sa.Column('order_id', sa.UUID(), nullable=True),
    sa.Column('movement_type', sa.String(length=20), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
    sa.Column('unit', sa.String(length=10), nullable=False),
    sa.Column('unit_cost_sar', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('movement_date', sa.Date(), nullable=False),
    sa.Column('transfer_group', sa.UUID(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], name=op.f('inventory_movements_batch_id_fkey')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('inventory_movements_company_id_fkey')),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('inventory_movements_created_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('inventory_movements_order_id_fkey')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('inventory_movements_product_id_fkey')),
    sa.ForeignKeyConstraint(['product_master_id'], ['product_masters.id'], name=op.f('inventory_movements_product_master_id_fkey')),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name=op.f('inventory_movements_warehouse_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('inventory_movements_pkey')),
    sa.UniqueConstraint('reference', name=op.f('inventory_movements_reference_key'))
    )
    op.create_index(op.f('ix_inventory_movements_company_id'), 'inventory_movements', ['company_id'], unique=False)
    op.create_index('ix_inventory_movements_company_product', 'inventory_movements', ['company_id', 'product_id'], unique=False)
    op.create_index(op.f('ix_inventory_movements_order_id'), 'inventory_movements', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inventory_movements_order_id'), table_name='inventory_movements')
    op.drop_index('ix_inventory_movements_company_product', table_name='inventory_movements')
    op.drop_index(op.f('ix_inventory_movements_company_id'), table_name='inventory_movements')
    op.drop_table('inventory_movements')
