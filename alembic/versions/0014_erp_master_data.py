"""ERP master data: 20 master tables, product master catalog, batch/lot traceability

Revision ID: 0014_erp_master_data
Revises: 0013_platform_settings
Create Date: 2026-09-28

Batch I — ERP Master Data (Minerals_ERP_Master_Data.pdf §13, all 20 masters):
mineral groups/types/grades, units of measure, particle sizes, packaging,
quality parameters/test methods/specifications, regions, mine sources,
warehouses/bins, applications, customer segments, HS codes, incoterms,
payment terms, subscription plans, the Product Master catalog (+ packaging
and application links), and Batch/Lot with quality results.

Purely additive: no existing table is touched. Starter reference data is NOT
inserted here — it is loaded from the admin UI ("Load starter data") or
`python scripts/load_master_data.py`, so it stays editable and re-runnable
(idempotent upsert by code) instead of being frozen into a migration.

Enum note: the three batch enums are created implicitly by create_table's
sa.Enum and dropped explicitly in downgrade() (checkfirst) — they are new
types, so the create_type=False rule from 0001 (which guards against
re-creating an EXISTING type) does not apply.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # noqa: F401

# revision identifiers, used by Alembic.
revision = "0014_erp_master_data"
down_revision = "0013_platform_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('applications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('applications_pkey'))
    )
    op.create_index(op.f('ix_applications_code'), 'applications', ['code'], unique=True)
    op.create_table('customer_segments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('customer_segments_pkey'))
    )
    op.create_index(op.f('ix_customer_segments_code'), 'customer_segments', ['code'], unique=True)
    op.create_table('hs_codes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('national_tariff_code', sa.String(length=20), nullable=True),
    sa.Column('customs_duty_pct', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('sds_required', sa.Boolean(), nullable=False),
    sa.Column('hazard_class', sa.String(length=40), nullable=True),
    sa.Column('export_license_required', sa.Boolean(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('hs_codes_pkey'))
    )
    op.create_index(op.f('ix_hs_codes_code'), 'hs_codes', ['code'], unique=True)
    op.create_table('incoterms',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('edition', sa.String(length=10), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('incoterms_pkey'))
    )
    op.create_index(op.f('ix_incoterms_code'), 'incoterms', ['code'], unique=True)
    op.create_table('mineral_groups',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('mineral_groups_pkey'))
    )
    op.create_index(op.f('ix_mineral_groups_code'), 'mineral_groups', ['code'], unique=True)
    op.create_table('particle_sizes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('mesh', sa.Integer(), nullable=True),
    sa.Column('micron_min', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('micron_max', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('d50_micron', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('d90_micron', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('particle_sizes_pkey'))
    )
    op.create_index(op.f('ix_particle_sizes_code'), 'particle_sizes', ['code'], unique=True)
    op.create_table('payment_terms',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('days', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('payment_terms_pkey'))
    )
    op.create_index(op.f('ix_payment_terms_code'), 'payment_terms', ['code'], unique=True)
    op.create_table('regions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('country_code', sa.String(length=2), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('regions_pkey'))
    )
    op.create_index(op.f('ix_regions_code'), 'regions', ['code'], unique=True)
    op.create_table('subscription_plans',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('annual_price_sar', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('max_active_listings', sa.Integer(), nullable=True),
    sa.Column('max_active_rfqs', sa.Integer(), nullable=True),
    sa.Column('search_priority', sa.Integer(), nullable=False),
    sa.Column('expedited_passport_review', sa.Boolean(), nullable=False),
    sa.Column('priority_lab_scheduling', sa.Boolean(), nullable=False),
    sa.Column('analytics_level', sa.String(length=20), nullable=False),
    sa.Column('dedicated_support', sa.Boolean(), nullable=False),
    sa.Column('grace_period_days', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('subscription_plans_pkey'))
    )
    op.create_index(op.f('ix_subscription_plans_code'), 'subscription_plans', ['code'], unique=True)
    op.create_table('test_methods',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('standard_ref', sa.String(length=80), nullable=True),
    sa.Column('default_fee_sar', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('turnaround_days', sa.Integer(), nullable=True),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('test_methods_pkey'))
    )
    op.create_index(op.f('ix_test_methods_code'), 'test_methods', ['code'], unique=True)
    op.create_table('units_of_measure',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('uom_type', sa.String(length=20), nullable=False),
    sa.Column('symbol', sa.String(length=20), nullable=True),
    sa.Column('factor_to_base', sa.Numeric(precision=24, scale=10), nullable=False),
    sa.Column('is_base', sa.Boolean(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('units_of_measure_pkey'))
    )
    op.create_index(op.f('ix_units_of_measure_code'), 'units_of_measure', ['code'], unique=True)
    op.create_table('mineral_types',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('group_id', sa.UUID(), nullable=False),
    sa.Column('chemical_formula', sa.String(length=40), nullable=True),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['mineral_groups.id'], name=op.f('mineral_types_group_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('mineral_types_pkey'))
    )
    op.create_index(op.f('ix_mineral_types_code'), 'mineral_types', ['code'], unique=True)
    op.create_index(op.f('ix_mineral_types_group_id'), 'mineral_types', ['group_id'], unique=False)
    op.create_table('packaging_types',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('capacity_value', sa.Numeric(precision=14, scale=3), nullable=True),
    sa.Column('capacity_uom_id', sa.UUID(), nullable=True),
    sa.Column('material', sa.String(length=60), nullable=True),
    sa.Column('is_bulk', sa.Boolean(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['capacity_uom_id'], ['units_of_measure.id'], name=op.f('packaging_types_capacity_uom_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('packaging_types_pkey'))
    )
    op.create_index(op.f('ix_packaging_types_code'), 'packaging_types', ['code'], unique=True)
    op.create_table('quality_parameters',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('parameter_type', sa.String(length=20), nullable=False),
    sa.Column('symbol', sa.String(length=30), nullable=True),
    sa.Column('default_uom_id', sa.UUID(), nullable=True),
    sa.Column('default_test_method_id', sa.UUID(), nullable=True),
    sa.Column('decimal_places', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['default_test_method_id'], ['test_methods.id'], name=op.f('quality_parameters_default_test_method_id_fkey')),
    sa.ForeignKeyConstraint(['default_uom_id'], ['units_of_measure.id'], name=op.f('quality_parameters_default_uom_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('quality_parameters_pkey'))
    )
    op.create_index(op.f('ix_quality_parameters_code'), 'quality_parameters', ['code'], unique=True)
    op.create_table('warehouses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=True),
    sa.Column('region_id', sa.UUID(), nullable=True),
    sa.Column('city', sa.String(length=80), nullable=True),
    sa.Column('national_address', sa.String(length=20), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('capacity_mt', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('warehouses_company_id_fkey')),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], name=op.f('warehouses_region_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('warehouses_pkey'))
    )
    op.create_index(op.f('ix_warehouses_code'), 'warehouses', ['code'], unique=True)
    op.create_index(op.f('ix_warehouses_company_id'), 'warehouses', ['company_id'], unique=False)
    op.create_table('grades',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('mineral_type_id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=True),
    sa.Column('purity_min_pct', sa.Numeric(precision=7, scale=3), nullable=True),
    sa.Column('quality_level', sa.String(length=10), nullable=True),
    sa.Column('spec_version', sa.String(length=20), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=True),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], name=op.f('grades_application_id_fkey')),
    sa.ForeignKeyConstraint(['mineral_type_id'], ['mineral_types.id'], name=op.f('grades_mineral_type_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('grades_pkey'))
    )
    op.create_index(op.f('ix_grades_code'), 'grades', ['code'], unique=True)
    op.create_index(op.f('ix_grades_mineral_type_id'), 'grades', ['mineral_type_id'], unique=False)
    op.create_table('mine_sources',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('mineral_type_id', sa.UUID(), nullable=True),
    sa.Column('region_id', sa.UUID(), nullable=True),
    sa.Column('owner_company_id', sa.UUID(), nullable=True),
    sa.Column('owner_name', sa.String(length=150), nullable=True),
    sa.Column('location', sa.String(length=150), nullable=True),
    sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('license_number', sa.String(length=60), nullable=True),
    sa.Column('license_expiry', sa.Date(), nullable=True),
    sa.Column('extraction_method', sa.String(length=30), nullable=True),
    sa.Column('country_of_origin', sa.String(length=2), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['mineral_type_id'], ['mineral_types.id'], name=op.f('mine_sources_mineral_type_id_fkey')),
    sa.ForeignKeyConstraint(['owner_company_id'], ['companies.id'], name=op.f('mine_sources_owner_company_id_fkey')),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], name=op.f('mine_sources_region_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('mine_sources_pkey'))
    )
    op.create_index(op.f('ix_mine_sources_code'), 'mine_sources', ['code'], unique=True)
    op.create_index(op.f('ix_mine_sources_owner_company_id'), 'mine_sources', ['owner_company_id'], unique=False)
    op.create_table('warehouse_bins',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('warehouse_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('capacity_mt', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name=op.f('warehouse_bins_warehouse_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('warehouse_bins_pkey')),
    sa.UniqueConstraint('warehouse_id', 'code', name='uq_warehouse_bin_code')
    )
    op.create_index(op.f('ix_warehouse_bins_warehouse_id'), 'warehouse_bins', ['warehouse_id'], unique=False)
    op.create_table('product_masters',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('short_name', sa.String(length=60), nullable=True),
    sa.Column('product_type', sa.String(length=30), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('mineral_type_id', sa.UUID(), nullable=False),
    sa.Column('grade_id', sa.UUID(), nullable=True),
    sa.Column('particle_size_id', sa.UUID(), nullable=True),
    sa.Column('quality_class', sa.String(length=10), nullable=True),
    sa.Column('chemical_formula', sa.String(length=40), nullable=True),
    sa.Column('color', sa.String(length=40), nullable=True),
    sa.Column('processing_method', sa.String(length=80), nullable=True),
    sa.Column('origin_country', sa.String(length=2), nullable=False),
    sa.Column('default_source_id', sa.UUID(), nullable=True),
    sa.Column('hs_code_id', sa.UUID(), nullable=True),
    sa.Column('sds_required', sa.Boolean(), nullable=False),
    sa.Column('hazard_class', sa.String(length=40), nullable=True),
    sa.Column('is_sales_item', sa.Boolean(), nullable=False),
    sa.Column('is_purchase_item', sa.Boolean(), nullable=False),
    sa.Column('is_inventory_item', sa.Boolean(), nullable=False),
    sa.Column('standard_cost', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('selling_price', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('base_uom_id', sa.UUID(), nullable=True),
    sa.Column('purchase_uom_id', sa.UUID(), nullable=True),
    sa.Column('sales_uom_id', sa.UUID(), nullable=True),
    sa.Column('batch_managed', sa.Boolean(), nullable=False),
    sa.Column('default_warehouse_id', sa.UUID(), nullable=True),
    sa.Column('coa_required', sa.Boolean(), nullable=False),
    sa.Column('inspection_required', sa.Boolean(), nullable=False),
    sa.Column('bulk_density_t_m3', sa.Numeric(precision=8, scale=3), nullable=True),
    sa.Column('loading_type', sa.String(length=40), nullable=True),
    sa.Column('transport_requirements', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name_en', sa.String(length=150), nullable=False),
    sa.Column('name_ar', sa.String(length=150), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['base_uom_id'], ['units_of_measure.id'], name=op.f('product_masters_base_uom_id_fkey')),
    sa.ForeignKeyConstraint(['default_source_id'], ['mine_sources.id'], name=op.f('product_masters_default_source_id_fkey')),
    sa.ForeignKeyConstraint(['default_warehouse_id'], ['warehouses.id'], name=op.f('product_masters_default_warehouse_id_fkey')),
    sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], name=op.f('product_masters_grade_id_fkey')),
    sa.ForeignKeyConstraint(['hs_code_id'], ['hs_codes.id'], name=op.f('product_masters_hs_code_id_fkey')),
    sa.ForeignKeyConstraint(['mineral_type_id'], ['mineral_types.id'], name=op.f('product_masters_mineral_type_id_fkey')),
    sa.ForeignKeyConstraint(['particle_size_id'], ['particle_sizes.id'], name=op.f('product_masters_particle_size_id_fkey')),
    sa.ForeignKeyConstraint(['purchase_uom_id'], ['units_of_measure.id'], name=op.f('product_masters_purchase_uom_id_fkey')),
    sa.ForeignKeyConstraint(['sales_uom_id'], ['units_of_measure.id'], name=op.f('product_masters_sales_uom_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('product_masters_pkey'))
    )
    op.create_index(op.f('ix_product_masters_code'), 'product_masters', ['code'], unique=True)
    op.create_index(op.f('ix_product_masters_mineral_type_id'), 'product_masters', ['mineral_type_id'], unique=False)
    op.create_table('product_master_applications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('product_master_id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], name=op.f('product_master_applications_application_id_fkey')),
    sa.ForeignKeyConstraint(['product_master_id'], ['product_masters.id'], name=op.f('product_master_applications_product_master_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('product_master_applications_pkey')),
    sa.UniqueConstraint('product_master_id', 'application_id', name='uq_pm_application')
    )
    op.create_index(op.f('ix_product_master_applications_product_master_id'), 'product_master_applications', ['product_master_id'], unique=False)
    op.create_table('product_master_packagings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('product_master_id', sa.UUID(), nullable=False),
    sa.Column('packaging_type_id', sa.UUID(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['packaging_type_id'], ['packaging_types.id'], name=op.f('product_master_packagings_packaging_type_id_fkey')),
    sa.ForeignKeyConstraint(['product_master_id'], ['product_masters.id'], name=op.f('product_master_packagings_product_master_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('product_master_packagings_pkey')),
    sa.UniqueConstraint('product_master_id', 'packaging_type_id', name='uq_pm_packaging')
    )
    op.create_index(op.f('ix_product_master_packagings_product_master_id'), 'product_master_packagings', ['product_master_id'], unique=False)
    op.create_table('quality_specifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('grade_id', sa.UUID(), nullable=True),
    sa.Column('product_master_id', sa.UUID(), nullable=True),
    sa.Column('parameter_id', sa.UUID(), nullable=False),
    sa.Column('min_value', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('max_value', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('target_value', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('uom_id', sa.UUID(), nullable=True),
    sa.Column('test_method_id', sa.UUID(), nullable=True),
    sa.Column('is_mandatory', sa.Boolean(), nullable=False),
    sa.Column('spec_version', sa.String(length=20), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('(grade_id IS NOT NULL) <> (product_master_id IS NOT NULL)', name='ck_quality_spec_grade_xor_product'),
    sa.CheckConstraint('min_value IS NULL OR max_value IS NULL OR min_value <= max_value', name='ck_quality_spec_min_le_max'),
    sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], name=op.f('quality_specifications_grade_id_fkey')),
    sa.ForeignKeyConstraint(['parameter_id'], ['quality_parameters.id'], name=op.f('quality_specifications_parameter_id_fkey')),
    sa.ForeignKeyConstraint(['product_master_id'], ['product_masters.id'], name=op.f('quality_specifications_product_master_id_fkey')),
    sa.ForeignKeyConstraint(['test_method_id'], ['test_methods.id'], name=op.f('quality_specifications_test_method_id_fkey')),
    sa.ForeignKeyConstraint(['uom_id'], ['units_of_measure.id'], name=op.f('quality_specifications_uom_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('quality_specifications_pkey'))
    )
    op.create_index(op.f('ix_quality_specifications_grade_id'), 'quality_specifications', ['grade_id'], unique=False)
    op.create_index(op.f('ix_quality_specifications_product_master_id'), 'quality_specifications', ['product_master_id'], unique=False)
    op.create_table('batches',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('batch_number', sa.String(length=40), nullable=False),
    sa.Column('lot_number', sa.String(length=40), nullable=True),
    sa.Column('source_batch_ref', sa.String(length=60), nullable=True),
    sa.Column('product_master_id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=True),
    sa.Column('listing_product_id', sa.UUID(), nullable=True),
    sa.Column('mine_source_id', sa.UUID(), nullable=True),
    sa.Column('parent_batch_id', sa.UUID(), nullable=True),
    sa.Column('stage', sa.Enum('extraction', 'processing', 'finished', name='batch_stage'), nullable=False),
    sa.Column('production_date', sa.Date(), nullable=True),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
    sa.Column('uom_id', sa.UUID(), nullable=True),
    sa.Column('warehouse_id', sa.UUID(), nullable=True),
    sa.Column('bin_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Enum('quarantine', 'released', 'rejected', 'blocked', 'consumed', name='batch_status'), nullable=False),
    sa.Column('qc_status', sa.Enum('pending', 'passed', 'failed', name='qc_status'), nullable=False),
    sa.Column('qc_evaluated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('released_by_user_id', sa.UUID(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['bin_id'], ['warehouse_bins.id'], name=op.f('batches_bin_id_fkey')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('batches_company_id_fkey')),
    sa.ForeignKeyConstraint(['listing_product_id'], ['products.id'], name=op.f('batches_listing_product_id_fkey')),
    sa.ForeignKeyConstraint(['mine_source_id'], ['mine_sources.id'], name=op.f('batches_mine_source_id_fkey')),
    sa.ForeignKeyConstraint(['parent_batch_id'], ['batches.id'], name=op.f('batches_parent_batch_id_fkey')),
    sa.ForeignKeyConstraint(['product_master_id'], ['product_masters.id'], name=op.f('batches_product_master_id_fkey')),
    sa.ForeignKeyConstraint(['released_by_user_id'], ['users.id'], name=op.f('batches_released_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['uom_id'], ['units_of_measure.id'], name=op.f('batches_uom_id_fkey')),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name=op.f('batches_warehouse_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('batches_pkey'))
    )
    op.create_index(op.f('ix_batches_batch_number'), 'batches', ['batch_number'], unique=True)
    op.create_index(op.f('ix_batches_company_id'), 'batches', ['company_id'], unique=False)
    op.create_index(op.f('ix_batches_listing_product_id'), 'batches', ['listing_product_id'], unique=False)
    op.create_index(op.f('ix_batches_product_master_id'), 'batches', ['product_master_id'], unique=False)
    op.create_table('batch_quality_results',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('batch_id', sa.UUID(), nullable=False),
    sa.Column('parameter_id', sa.UUID(), nullable=False),
    sa.Column('measured_value', sa.Numeric(precision=14, scale=4), nullable=False),
    sa.Column('spec_min', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('spec_max', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('uom_code', sa.String(length=20), nullable=True),
    sa.Column('test_method_id', sa.UUID(), nullable=True),
    sa.Column('passed', sa.Boolean(), nullable=True),
    sa.Column('certification_id', sa.UUID(), nullable=True),
    sa.Column('tested_at', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], name=op.f('batch_quality_results_batch_id_fkey')),
    sa.ForeignKeyConstraint(['certification_id'], ['certifications.id'], name=op.f('batch_quality_results_certification_id_fkey')),
    sa.ForeignKeyConstraint(['parameter_id'], ['quality_parameters.id'], name=op.f('batch_quality_results_parameter_id_fkey')),
    sa.ForeignKeyConstraint(['test_method_id'], ['test_methods.id'], name=op.f('batch_quality_results_test_method_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('batch_quality_results_pkey'))
    )
    op.create_index(op.f('ix_batch_quality_results_batch_id'), 'batch_quality_results', ['batch_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_batch_quality_results_batch_id'), table_name='batch_quality_results')
    op.drop_table('batch_quality_results')
    op.drop_index(op.f('ix_batches_product_master_id'), table_name='batches')
    op.drop_index(op.f('ix_batches_listing_product_id'), table_name='batches')
    op.drop_index(op.f('ix_batches_company_id'), table_name='batches')
    op.drop_index(op.f('ix_batches_batch_number'), table_name='batches')
    op.drop_table('batches')
    op.drop_index(op.f('ix_quality_specifications_product_master_id'), table_name='quality_specifications')
    op.drop_index(op.f('ix_quality_specifications_grade_id'), table_name='quality_specifications')
    op.drop_table('quality_specifications')
    op.drop_index(op.f('ix_product_master_packagings_product_master_id'), table_name='product_master_packagings')
    op.drop_table('product_master_packagings')
    op.drop_index(op.f('ix_product_master_applications_product_master_id'), table_name='product_master_applications')
    op.drop_table('product_master_applications')
    op.drop_index(op.f('ix_product_masters_mineral_type_id'), table_name='product_masters')
    op.drop_index(op.f('ix_product_masters_code'), table_name='product_masters')
    op.drop_table('product_masters')
    op.drop_index(op.f('ix_warehouse_bins_warehouse_id'), table_name='warehouse_bins')
    op.drop_table('warehouse_bins')
    op.drop_index(op.f('ix_mine_sources_owner_company_id'), table_name='mine_sources')
    op.drop_index(op.f('ix_mine_sources_code'), table_name='mine_sources')
    op.drop_table('mine_sources')
    op.drop_index(op.f('ix_grades_mineral_type_id'), table_name='grades')
    op.drop_index(op.f('ix_grades_code'), table_name='grades')
    op.drop_table('grades')
    op.drop_index(op.f('ix_warehouses_company_id'), table_name='warehouses')
    op.drop_index(op.f('ix_warehouses_code'), table_name='warehouses')
    op.drop_table('warehouses')
    op.drop_index(op.f('ix_quality_parameters_code'), table_name='quality_parameters')
    op.drop_table('quality_parameters')
    op.drop_index(op.f('ix_packaging_types_code'), table_name='packaging_types')
    op.drop_table('packaging_types')
    op.drop_index(op.f('ix_mineral_types_group_id'), table_name='mineral_types')
    op.drop_index(op.f('ix_mineral_types_code'), table_name='mineral_types')
    op.drop_table('mineral_types')
    op.drop_index(op.f('ix_units_of_measure_code'), table_name='units_of_measure')
    op.drop_table('units_of_measure')
    op.drop_index(op.f('ix_test_methods_code'), table_name='test_methods')
    op.drop_table('test_methods')
    op.drop_index(op.f('ix_subscription_plans_code'), table_name='subscription_plans')
    op.drop_table('subscription_plans')
    op.drop_index(op.f('ix_regions_code'), table_name='regions')
    op.drop_table('regions')
    op.drop_index(op.f('ix_payment_terms_code'), table_name='payment_terms')
    op.drop_table('payment_terms')
    op.drop_index(op.f('ix_particle_sizes_code'), table_name='particle_sizes')
    op.drop_table('particle_sizes')
    op.drop_index(op.f('ix_mineral_groups_code'), table_name='mineral_groups')
    op.drop_table('mineral_groups')
    op.drop_index(op.f('ix_incoterms_code'), table_name='incoterms')
    op.drop_table('incoterms')
    op.drop_index(op.f('ix_hs_codes_code'), table_name='hs_codes')
    op.drop_table('hs_codes')
    op.drop_index(op.f('ix_customer_segments_code'), table_name='customer_segments')
    op.drop_table('customer_segments')
    op.drop_index(op.f('ix_applications_code'), table_name='applications')
    op.drop_table('applications')
    # Enum types were created implicitly by create_table (sa.Enum) — drop them explicitly.
    for enum_name in ("qc_status", "batch_status", "batch_stage"):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
