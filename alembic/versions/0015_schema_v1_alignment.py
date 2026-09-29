"""Schema V1 alignment: bilingual/regulatory company fields, specs, COA results, references, financial snapshot, fees, reveal log, documents

Revision ID: 0015_schema_v1_alignment
Revises: 0014_erp_master_data
Create Date: 2026-09-28

Batch J — align the live schema with Minerals_DB_Schema_V1.txt without
breaking anything built in Phases 1–2 or Batches A–H. Additive only:

  companies        + company_name_ar, region_id, city, national_address,
                     customer_segment_id, license_valid_until, license_verified,
                     is_founding_member, subscription_valid_until
  users            + phone, job_title, company_role          (V1 user_profiles)
  products         + product_master_id, name_en/ar, region_id, min_order_qty,
                     incoterm_id, packaging_type_id, mine_source_id,
                     is_visible_to_buyers, created_by_user_id
  verification_req + request_reference, collection_date, field_officer,
                     sample_id, fee_sar, completed_at, notes, batch_id  (V1 lab_requests)
  certifications   + analyst_name, sample/test dates, all_parameters_pass,
                     file_path/file_hash, signed_off_*, fee_sar,
                     source_certification_id, batch_id     (V1 coas + mineral_passports)
  rfqs             + rfq_reference, product_master_id, grade_id, required_by,
                     incoterm_id, payment_terms_days, closes_at, created_by
  quotations       + quotation_reference, product_id, coa/passport ids,
                     total_price, payment_terms_days, incoterm_id,
                     validity_days, valid_until, match_score, submitted_by
  orders           + order_reference + frozen financial snapshot incl. VAT,
                     identity_revealed_at, settlement fee amounts, cancellation
  notifications    + company_id, title_ar, body_ar, action_url, email/sms flags
  NEW tables       product_specs, rfq_specs, certification_results (V1 coa_results),
                   reveal_logs, order_documents, settlement_fees, document_sequences
  Enum values      rfq_status+cancelled, quotation_status+rejected/expired,
                   order_status+invoiced/disputed/resolved/cancelled

Where V1 and this codebase deliberately differ (documented in
docs/SCHEMA_V1_MAPPING.md): V1 `coas` + `mineral_passports` stay consolidated
in `certifications` (Batch A decision); V1 `lab_requests` = `verification_requests`;
V1 tier names bronze/silver/gold are display names on subscription_plans over
the BRD's entry/mid/premium keys; V1 `auth.users` (Supabase) = our `users`.

Backfills existing orders' financial snapshot and assigns references to
existing rows (RFQ-YYYY-00001 ...), seeding document_sequences to match.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # noqa: F401

# revision identifiers, used by Alembic.
revision = "0015_schema_v1_alignment"
down_revision = "0014_erp_master_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 0. Extend existing workflow enums (Schema V1 status values). ---
    # ALTER TYPE ... ADD VALUE can't be undone in PostgreSQL (no DROP VALUE);
    # downgrade() leaves these values in place, which is harmless because no
    # row written by pre-0015 code can hold them.
    for enum_name, values in (
        ("rfq_status", ("cancelled",)),
        ("quotation_status", ("rejected", "expired")),
        ("order_status", ("invoiced", "disputed", "resolved", "cancelled")),
    ):
        for value in values:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table('document_sequences',
    sa.Column('sequence_key', sa.String(length=30), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('last_number', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('sequence_key', 'year', name=op.f('document_sequences_pkey'))
    )
    op.create_table('product_specs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('parameter_id', sa.UUID(), nullable=True),
    sa.Column('parameter', sa.String(length=80), nullable=False),
    sa.Column('min_value', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('max_value', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('test_method', sa.String(length=80), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['parameter_id'], ['quality_parameters.id'], name=op.f('product_specs_parameter_id_fkey')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('product_specs_product_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('product_specs_pkey'))
    )
    op.create_index(op.f('ix_product_specs_product_id'), 'product_specs', ['product_id'], unique=False)
    op.create_table('rfq_specs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('rfq_id', sa.UUID(), nullable=False),
    sa.Column('parameter_id', sa.UUID(), nullable=True),
    sa.Column('parameter', sa.String(length=80), nullable=False),
    sa.Column('min_value', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('max_value', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['parameter_id'], ['quality_parameters.id'], name=op.f('rfq_specs_parameter_id_fkey')),
    sa.ForeignKeyConstraint(['rfq_id'], ['rfqs.id'], name=op.f('rfq_specs_rfq_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('rfq_specs_pkey'))
    )
    op.create_index(op.f('ix_rfq_specs_rfq_id'), 'rfq_specs', ['rfq_id'], unique=False)
    op.create_table('certification_results',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('certification_id', sa.UUID(), nullable=False),
    sa.Column('parameter_id', sa.UUID(), nullable=True),
    sa.Column('parameter', sa.String(length=80), nullable=False),
    sa.Column('required_min', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('required_max', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('measured_value', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('test_method', sa.String(length=80), nullable=True),
    sa.Column('passed', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['certification_id'], ['certifications.id'], name=op.f('certification_results_certification_id_fkey')),
    sa.ForeignKeyConstraint(['parameter_id'], ['quality_parameters.id'], name=op.f('certification_results_parameter_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('certification_results_pkey'))
    )
    op.create_index(op.f('ix_certification_results_certification_id'), 'certification_results', ['certification_id'], unique=False)
    op.create_table('order_documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('document_type', sa.String(length=40), nullable=False),
    sa.Column('file_path', sa.String(length=255), nullable=True),
    sa.Column('file_hash', sa.String(length=64), nullable=True),
    sa.Column('uploaded_by_user_id', sa.UUID(), nullable=True),
    sa.Column('visible_to_buyer', sa.Boolean(), nullable=False),
    sa.Column('visible_to_seller', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('order_documents_order_id_fkey')),
    sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], name=op.f('order_documents_uploaded_by_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('order_documents_pkey'))
    )
    op.create_index(op.f('ix_order_documents_order_id'), 'order_documents', ['order_id'], unique=False)
    op.create_table('reveal_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('buyer_company_id', sa.UUID(), nullable=False),
    sa.Column('seller_company_id', sa.UUID(), nullable=False),
    sa.Column('triggered_by', sa.String(length=50), nullable=False),
    sa.Column('triggered_by_user_id', sa.UUID(), nullable=True),
    sa.Column('revealed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['buyer_company_id'], ['companies.id'], name=op.f('reveal_logs_buyer_company_id_fkey')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('reveal_logs_order_id_fkey')),
    sa.ForeignKeyConstraint(['seller_company_id'], ['companies.id'], name=op.f('reveal_logs_seller_company_id_fkey')),
    sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], name=op.f('reveal_logs_triggered_by_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('reveal_logs_pkey'))
    )
    op.create_index(op.f('ix_reveal_logs_order_id'), 'reveal_logs', ['order_id'], unique=False)
    op.create_table('settlement_fees',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('paid_by_company_id', sa.UUID(), nullable=False),
    sa.Column('party', sa.String(length=10), nullable=False),
    sa.Column('amount_sar', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('vat_rate_pct', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('vat_amount_sar', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total_sar', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('status', sa.Enum('pending', 'paid', 'failed', 'refunded', 'waived', name='settlement_fee_status'), nullable=False),
    sa.Column('gateway', sa.String(length=30), nullable=True),
    sa.Column('gateway_payment_id', sa.String(length=100), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('recorded_by_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('settlement_fees_order_id_fkey')),
    sa.ForeignKeyConstraint(['paid_by_company_id'], ['companies.id'], name=op.f('settlement_fees_paid_by_company_id_fkey')),
    sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], name=op.f('settlement_fees_recorded_by_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('settlement_fees_pkey'))
    )
    op.create_index(op.f('ix_settlement_fees_order_id'), 'settlement_fees', ['order_id'], unique=False)
    op.add_column('certifications', sa.Column('analyst_name', sa.String(length=120), nullable=True))
    op.add_column('certifications', sa.Column('sample_collected_at', sa.Date(), nullable=True))
    op.add_column('certifications', sa.Column('test_completed_at', sa.Date(), nullable=True))
    op.add_column('certifications', sa.Column('all_parameters_pass', sa.Boolean(), nullable=True))
    op.add_column('certifications', sa.Column('file_path', sa.String(length=255), nullable=True))
    op.add_column('certifications', sa.Column('file_hash', sa.String(length=64), nullable=True))
    op.add_column('certifications', sa.Column('signed_off_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('certifications', sa.Column('signed_off_by_user_id', sa.UUID(), nullable=True))
    op.add_column('certifications', sa.Column('fee_sar', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('certifications', sa.Column('source_certification_id', sa.UUID(), nullable=True))
    op.add_column('certifications', sa.Column('batch_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('certifications_signed_off_by_user_id_fkey'), 'certifications', 'users', ['signed_off_by_user_id'], ['id'])
    op.create_foreign_key(op.f('certifications_batch_id_fkey'), 'certifications', 'batches', ['batch_id'], ['id'])
    op.create_foreign_key(op.f('certifications_source_certification_id_fkey'), 'certifications', 'certifications', ['source_certification_id'], ['id'])
    op.add_column('companies', sa.Column('company_name_ar', sa.String(length=255), nullable=True))
    op.add_column('companies', sa.Column('region_id', sa.UUID(), nullable=True))
    op.add_column('companies', sa.Column('city', sa.String(length=80), nullable=True))
    op.add_column('companies', sa.Column('national_address', sa.String(length=20), nullable=True))
    op.add_column('companies', sa.Column('customer_segment_id', sa.UUID(), nullable=True))
    op.add_column('companies', sa.Column('license_valid_until', sa.Date(), nullable=True))
    op.add_column('companies', sa.Column('license_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('companies', sa.Column('is_founding_member', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('companies', sa.Column('subscription_valid_until', sa.Date(), nullable=True))
    op.create_foreign_key(op.f('companies_customer_segment_id_fkey'), 'companies', 'customer_segments', ['customer_segment_id'], ['id'])
    op.create_foreign_key(op.f('companies_region_id_fkey'), 'companies', 'regions', ['region_id'], ['id'])
    op.add_column('notifications', sa.Column('company_id', sa.UUID(), nullable=True))
    op.add_column('notifications', sa.Column('title_ar', sa.String(length=200), nullable=True))
    op.add_column('notifications', sa.Column('body_ar', sa.Text(), nullable=True))
    op.add_column('notifications', sa.Column('action_url', sa.String(length=255), nullable=True))
    op.add_column('notifications', sa.Column('email_sent', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('notifications', sa.Column('sms_sent', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(op.f('ix_notifications_company_id'), 'notifications', ['company_id'], unique=False)
    op.create_foreign_key(op.f('notifications_company_id_fkey'), 'notifications', 'companies', ['company_id'], ['id'])
    op.add_column('orders', sa.Column('order_reference', sa.String(length=30), nullable=True))
    op.add_column('orders', sa.Column('product_id', sa.UUID(), nullable=True))
    op.add_column('orders', sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=True))
    op.add_column('orders', sa.Column('quantity_unit', sa.String(length=20), nullable=True))
    op.add_column('orders', sa.Column('price_per_unit', sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column('orders', sa.Column('currency', sa.String(length=3), nullable=False, server_default='SAR'))
    op.add_column('orders', sa.Column('subtotal_sar', sa.Numeric(precision=16, scale=2), nullable=True))
    op.add_column('orders', sa.Column('vat_rate_pct', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('orders', sa.Column('vat_amount_sar', sa.Numeric(precision=16, scale=2), nullable=True))
    op.add_column('orders', sa.Column('total_value_sar', sa.Numeric(precision=16, scale=2), nullable=True))
    op.add_column('orders', sa.Column('delivery_location', sa.String(length=150), nullable=True))
    op.add_column('orders', sa.Column('required_by', sa.Date(), nullable=True))
    op.add_column('orders', sa.Column('incoterm_code', sa.String(length=10), nullable=True))
    op.add_column('orders', sa.Column('payment_terms_days', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('identity_revealed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('settlement_fee_buyer_sar', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('orders', sa.Column('settlement_fee_seller_sar', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('orders', sa.Column('settlement_fee_paid_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('cancellation_reason', sa.Text(), nullable=True))
    op.create_unique_constraint(op.f('orders_order_reference_key'), 'orders', ['order_reference'])
    op.create_foreign_key(op.f('orders_product_id_fkey'), 'orders', 'products', ['product_id'], ['id'])
    op.add_column('products', sa.Column('product_master_id', sa.UUID(), nullable=True))
    op.add_column('products', sa.Column('name_en', sa.String(length=150), nullable=True))
    op.add_column('products', sa.Column('name_ar', sa.String(length=150), nullable=True))
    op.add_column('products', sa.Column('region_id', sa.UUID(), nullable=True))
    op.add_column('products', sa.Column('min_order_qty', sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column('products', sa.Column('incoterm_id', sa.UUID(), nullable=True))
    op.add_column('products', sa.Column('packaging_type_id', sa.UUID(), nullable=True))
    op.add_column('products', sa.Column('mine_source_id', sa.UUID(), nullable=True))
    op.add_column('products', sa.Column('is_visible_to_buyers', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('products', sa.Column('created_by_user_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_products_product_master_id'), 'products', ['product_master_id'], unique=False)
    op.create_foreign_key(op.f('products_created_by_user_id_fkey'), 'products', 'users', ['created_by_user_id'], ['id'])
    op.create_foreign_key(op.f('products_incoterm_id_fkey'), 'products', 'incoterms', ['incoterm_id'], ['id'])
    op.create_foreign_key(op.f('products_packaging_type_id_fkey'), 'products', 'packaging_types', ['packaging_type_id'], ['id'])
    op.create_foreign_key(op.f('products_product_master_id_fkey'), 'products', 'product_masters', ['product_master_id'], ['id'])
    op.create_foreign_key(op.f('products_region_id_fkey'), 'products', 'regions', ['region_id'], ['id'])
    op.create_foreign_key(op.f('products_mine_source_id_fkey'), 'products', 'mine_sources', ['mine_source_id'], ['id'])
    op.add_column('quotations', sa.Column('quotation_reference', sa.String(length=30), nullable=True))
    op.add_column('quotations', sa.Column('product_id', sa.UUID(), nullable=True))
    op.add_column('quotations', sa.Column('coa_certification_id', sa.UUID(), nullable=True))
    op.add_column('quotations', sa.Column('passport_certification_id', sa.UUID(), nullable=True))
    op.add_column('quotations', sa.Column('total_price', sa.Numeric(precision=16, scale=2), nullable=True))
    op.add_column('quotations', sa.Column('payment_terms_days', sa.Integer(), nullable=True))
    op.add_column('quotations', sa.Column('incoterm_id', sa.UUID(), nullable=True))
    op.add_column('quotations', sa.Column('validity_days', sa.Integer(), nullable=True))
    op.add_column('quotations', sa.Column('valid_until', sa.Date(), nullable=True))
    op.add_column('quotations', sa.Column('match_score', sa.Integer(), nullable=True))
    op.add_column('quotations', sa.Column('submitted_by_user_id', sa.UUID(), nullable=True))
    op.create_unique_constraint(op.f('quotations_quotation_reference_key'), 'quotations', ['quotation_reference'])
    op.create_foreign_key(op.f('quotations_incoterm_id_fkey'), 'quotations', 'incoterms', ['incoterm_id'], ['id'])
    op.create_foreign_key(op.f('quotations_passport_certification_id_fkey'), 'quotations', 'certifications', ['passport_certification_id'], ['id'])
    op.create_foreign_key(op.f('quotations_product_id_fkey'), 'quotations', 'products', ['product_id'], ['id'])
    op.create_foreign_key(op.f('quotations_submitted_by_user_id_fkey'), 'quotations', 'users', ['submitted_by_user_id'], ['id'])
    op.create_foreign_key(op.f('quotations_coa_certification_id_fkey'), 'quotations', 'certifications', ['coa_certification_id'], ['id'])
    op.add_column('rfqs', sa.Column('rfq_reference', sa.String(length=30), nullable=True))
    op.add_column('rfqs', sa.Column('product_master_id', sa.UUID(), nullable=True))
    op.add_column('rfqs', sa.Column('grade_id', sa.UUID(), nullable=True))
    op.add_column('rfqs', sa.Column('required_by', sa.Date(), nullable=True))
    op.add_column('rfqs', sa.Column('incoterm_id', sa.UUID(), nullable=True))
    op.add_column('rfqs', sa.Column('payment_terms_days', sa.Integer(), nullable=True))
    op.add_column('rfqs', sa.Column('closes_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('rfqs', sa.Column('created_by_user_id', sa.UUID(), nullable=True))
    op.create_unique_constraint(op.f('rfqs_rfq_reference_key'), 'rfqs', ['rfq_reference'])
    op.create_foreign_key(op.f('rfqs_created_by_user_id_fkey'), 'rfqs', 'users', ['created_by_user_id'], ['id'])
    op.create_foreign_key(op.f('rfqs_product_master_id_fkey'), 'rfqs', 'product_masters', ['product_master_id'], ['id'])
    op.create_foreign_key(op.f('rfqs_grade_id_fkey'), 'rfqs', 'grades', ['grade_id'], ['id'])
    op.create_foreign_key(op.f('rfqs_incoterm_id_fkey'), 'rfqs', 'incoterms', ['incoterm_id'], ['id'])
    op.add_column('users', sa.Column('phone', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('job_title', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('company_role', sa.String(length=20), nullable=False, server_default='owner'))
    op.add_column('verification_requests', sa.Column('request_reference', sa.String(length=30), nullable=True))
    op.add_column('verification_requests', sa.Column('collection_date', sa.Date(), nullable=True))
    op.add_column('verification_requests', sa.Column('field_officer', sa.String(length=120), nullable=True))
    op.add_column('verification_requests', sa.Column('sample_id', sa.String(length=60), nullable=True))
    op.add_column('verification_requests', sa.Column('fee_sar', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('verification_requests', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('verification_requests', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('verification_requests', sa.Column('batch_id', sa.UUID(), nullable=True))
    op.create_unique_constraint(op.f('verification_requests_request_reference_key'), 'verification_requests', ['request_reference'])
    op.create_foreign_key(op.f('verification_requests_batch_id_fkey'), 'verification_requests', 'batches', ['batch_id'], ['id'])

    # --- Backfill: freeze the financial snapshot on existing orders, and give
    # every existing RFQ / quotation / order / lab request a business reference
    # so the new unique columns are populated consistently. VAT at the KSA
    # standard 15% for pre-existing rows (settings are admin-editable from now on).
    op.execute("""
        UPDATE orders o SET
            product_id = q.product_id,
            quantity = r.quantity_value,
            quantity_unit = r.quantity_unit,
            price_per_unit = q.price_value,
            currency = q.price_currency,
            subtotal_sar = ROUND(q.price_value * r.quantity_value, 2),
            vat_rate_pct = 15.00,
            vat_amount_sar = ROUND(q.price_value * r.quantity_value * 0.15, 2),
            total_value_sar = ROUND(q.price_value * r.quantity_value * 1.15, 2),
            delivery_location = r.delivery_location,
            identity_revealed_at = o.confirmed_at
        FROM quotations q, rfqs r
        WHERE q.id = o.quotation_id AND r.id = o.rfq_id
    """)
    for table, column, prefix, key in (
        ("rfqs", "rfq_reference", "RFQ", "rfq"),
        ("quotations", "quotation_reference", "QUO", "quotation"),
        ("orders", "order_reference", "ORD", "order"),
        ("verification_requests", "request_reference", "LAB", "verification"),
    ):
        op.execute(f"""
            WITH numbered AS (
                SELECT id, EXTRACT(YEAR FROM created_at)::int AS yr,
                       ROW_NUMBER() OVER (PARTITION BY EXTRACT(YEAR FROM created_at) ORDER BY created_at, id) AS n
                FROM {table}
            )
            UPDATE {table} t SET {column} = '{prefix}-' || numbered.yr || '-' || LPAD(numbered.n::text, 5, '0')
            FROM numbered WHERE numbered.id = t.id
        """)
        op.execute(f"""
            INSERT INTO document_sequences (sequence_key, year, last_number, updated_at)
            SELECT '{key}', EXTRACT(YEAR FROM created_at)::int, COUNT(*), now()
            FROM {table} GROUP BY EXTRACT(YEAR FROM created_at)
        """)


def downgrade() -> None:
    op.drop_constraint(op.f('verification_requests_batch_id_fkey'), 'verification_requests', type_='foreignkey')
    op.drop_constraint(op.f('verification_requests_request_reference_key'), 'verification_requests', type_='unique')
    op.drop_column('verification_requests', 'batch_id')
    op.drop_column('verification_requests', 'notes')
    op.drop_column('verification_requests', 'completed_at')
    op.drop_column('verification_requests', 'fee_sar')
    op.drop_column('verification_requests', 'sample_id')
    op.drop_column('verification_requests', 'field_officer')
    op.drop_column('verification_requests', 'collection_date')
    op.drop_column('verification_requests', 'request_reference')
    op.drop_column('users', 'company_role')
    op.drop_column('users', 'job_title')
    op.drop_column('users', 'phone')
    op.drop_constraint(op.f('rfqs_incoterm_id_fkey'), 'rfqs', type_='foreignkey')
    op.drop_constraint(op.f('rfqs_grade_id_fkey'), 'rfqs', type_='foreignkey')
    op.drop_constraint(op.f('rfqs_product_master_id_fkey'), 'rfqs', type_='foreignkey')
    op.drop_constraint(op.f('rfqs_created_by_user_id_fkey'), 'rfqs', type_='foreignkey')
    op.drop_constraint(op.f('rfqs_rfq_reference_key'), 'rfqs', type_='unique')
    op.drop_column('rfqs', 'created_by_user_id')
    op.drop_column('rfqs', 'closes_at')
    op.drop_column('rfqs', 'payment_terms_days')
    op.drop_column('rfqs', 'incoterm_id')
    op.drop_column('rfqs', 'required_by')
    op.drop_column('rfqs', 'grade_id')
    op.drop_column('rfqs', 'product_master_id')
    op.drop_column('rfqs', 'rfq_reference')
    op.drop_constraint(op.f('quotations_coa_certification_id_fkey'), 'quotations', type_='foreignkey')
    op.drop_constraint(op.f('quotations_submitted_by_user_id_fkey'), 'quotations', type_='foreignkey')
    op.drop_constraint(op.f('quotations_product_id_fkey'), 'quotations', type_='foreignkey')
    op.drop_constraint(op.f('quotations_passport_certification_id_fkey'), 'quotations', type_='foreignkey')
    op.drop_constraint(op.f('quotations_incoterm_id_fkey'), 'quotations', type_='foreignkey')
    op.drop_constraint(op.f('quotations_quotation_reference_key'), 'quotations', type_='unique')
    op.drop_column('quotations', 'submitted_by_user_id')
    op.drop_column('quotations', 'match_score')
    op.drop_column('quotations', 'valid_until')
    op.drop_column('quotations', 'validity_days')
    op.drop_column('quotations', 'incoterm_id')
    op.drop_column('quotations', 'payment_terms_days')
    op.drop_column('quotations', 'total_price')
    op.drop_column('quotations', 'passport_certification_id')
    op.drop_column('quotations', 'coa_certification_id')
    op.drop_column('quotations', 'product_id')
    op.drop_column('quotations', 'quotation_reference')
    op.drop_constraint(op.f('products_mine_source_id_fkey'), 'products', type_='foreignkey')
    op.drop_constraint(op.f('products_region_id_fkey'), 'products', type_='foreignkey')
    op.drop_constraint(op.f('products_product_master_id_fkey'), 'products', type_='foreignkey')
    op.drop_constraint(op.f('products_packaging_type_id_fkey'), 'products', type_='foreignkey')
    op.drop_constraint(op.f('products_incoterm_id_fkey'), 'products', type_='foreignkey')
    op.drop_constraint(op.f('products_created_by_user_id_fkey'), 'products', type_='foreignkey')
    op.drop_index(op.f('ix_products_product_master_id'), table_name='products')
    op.drop_column('products', 'created_by_user_id')
    op.drop_column('products', 'is_visible_to_buyers')
    op.drop_column('products', 'mine_source_id')
    op.drop_column('products', 'packaging_type_id')
    op.drop_column('products', 'incoterm_id')
    op.drop_column('products', 'min_order_qty')
    op.drop_column('products', 'region_id')
    op.drop_column('products', 'name_ar')
    op.drop_column('products', 'name_en')
    op.drop_column('products', 'product_master_id')
    op.drop_constraint(op.f('orders_product_id_fkey'), 'orders', type_='foreignkey')
    op.drop_constraint(op.f('orders_order_reference_key'), 'orders', type_='unique')
    op.drop_column('orders', 'cancellation_reason')
    op.drop_column('orders', 'cancelled_at')
    op.drop_column('orders', 'settlement_fee_paid_at')
    op.drop_column('orders', 'settlement_fee_seller_sar')
    op.drop_column('orders', 'settlement_fee_buyer_sar')
    op.drop_column('orders', 'identity_revealed_at')
    op.drop_column('orders', 'payment_terms_days')
    op.drop_column('orders', 'incoterm_code')
    op.drop_column('orders', 'required_by')
    op.drop_column('orders', 'delivery_location')
    op.drop_column('orders', 'total_value_sar')
    op.drop_column('orders', 'vat_amount_sar')
    op.drop_column('orders', 'vat_rate_pct')
    op.drop_column('orders', 'subtotal_sar')
    op.drop_column('orders', 'currency')
    op.drop_column('orders', 'price_per_unit')
    op.drop_column('orders', 'quantity_unit')
    op.drop_column('orders', 'quantity')
    op.drop_column('orders', 'product_id')
    op.drop_column('orders', 'order_reference')
    op.drop_constraint(op.f('notifications_company_id_fkey'), 'notifications', type_='foreignkey')
    op.drop_index(op.f('ix_notifications_company_id'), table_name='notifications')
    op.drop_column('notifications', 'sms_sent')
    op.drop_column('notifications', 'email_sent')
    op.drop_column('notifications', 'action_url')
    op.drop_column('notifications', 'body_ar')
    op.drop_column('notifications', 'title_ar')
    op.drop_column('notifications', 'company_id')
    op.drop_constraint(op.f('companies_region_id_fkey'), 'companies', type_='foreignkey')
    op.drop_constraint(op.f('companies_customer_segment_id_fkey'), 'companies', type_='foreignkey')
    op.drop_column('companies', 'subscription_valid_until')
    op.drop_column('companies', 'is_founding_member')
    op.drop_column('companies', 'license_verified')
    op.drop_column('companies', 'license_valid_until')
    op.drop_column('companies', 'customer_segment_id')
    op.drop_column('companies', 'national_address')
    op.drop_column('companies', 'city')
    op.drop_column('companies', 'region_id')
    op.drop_column('companies', 'company_name_ar')
    op.drop_constraint(op.f('certifications_source_certification_id_fkey'), 'certifications', type_='foreignkey')
    op.drop_constraint(op.f('certifications_batch_id_fkey'), 'certifications', type_='foreignkey')
    op.drop_constraint(op.f('certifications_signed_off_by_user_id_fkey'), 'certifications', type_='foreignkey')
    op.drop_column('certifications', 'batch_id')
    op.drop_column('certifications', 'source_certification_id')
    op.drop_column('certifications', 'fee_sar')
    op.drop_column('certifications', 'signed_off_by_user_id')
    op.drop_column('certifications', 'signed_off_at')
    op.drop_column('certifications', 'file_hash')
    op.drop_column('certifications', 'file_path')
    op.drop_column('certifications', 'all_parameters_pass')
    op.drop_column('certifications', 'test_completed_at')
    op.drop_column('certifications', 'sample_collected_at')
    op.drop_column('certifications', 'analyst_name')
    op.drop_index(op.f('ix_settlement_fees_order_id'), table_name='settlement_fees')
    op.drop_table('settlement_fees')
    op.drop_index(op.f('ix_reveal_logs_order_id'), table_name='reveal_logs')
    op.drop_table('reveal_logs')
    op.drop_index(op.f('ix_order_documents_order_id'), table_name='order_documents')
    op.drop_table('order_documents')
    op.drop_index(op.f('ix_certification_results_certification_id'), table_name='certification_results')
    op.drop_table('certification_results')
    op.drop_index(op.f('ix_rfq_specs_rfq_id'), table_name='rfq_specs')
    op.drop_table('rfq_specs')
    op.drop_index(op.f('ix_product_specs_product_id'), table_name='product_specs')
    op.drop_table('product_specs')
    op.drop_table('document_sequences')
    postgresql.ENUM(name="settlement_fee_status").drop(op.get_bind(), checkfirst=True)
