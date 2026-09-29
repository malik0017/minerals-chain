"""BRD completion release: i18n catalog, admin roles + PDPL, disputes, lab roster, specs/renewal, order documents, subscription lifecycle

Revision ID: 0017_brd_completion
Revises: 0016_system_settings
Create Date: 2026-09-28

One additive migration for the BRD-completion release (the batches ship
together, so they upgrade together):

  R1  ui_translations                       Arabic UI catalog (admin-editable)
  Q1  users.admin_role, privacy_consent_*   admin permission levels, PDPL consent
      content_pages, data_requests          editable Privacy/Terms/Help, PDPL data-subject requests
  M1  disputes, dispute_messages,           BRD 6.7 + immutable ruling with an
      dispute_corrections                   append-only correction log
      orders.completed_via_dispute          normal vs dispute-resolved reporting
  M2  lab_partner_terms                     lab roster + commercial terms (BRD 6.8)
      verification_requests.scheduled_at / testing_started_at / is_priority
  M3  products.suspended_reason / status_before_suspension, rfqs.cancelled_at /
      cancel_reason, quotations.revision_no, certifications.renewal_of_id / is_expedited
  P1  orders.invoice_number / invoiced_at, order_documents metadata
  M4  subscription_status + 'grace', subscriptions.expiry_notified_at /
      changed_by / change_note, subscription_charges

Data: existing admins become super_admin; the stored TEST ENVIRONMENT banner
override is removed (banner now defaults off).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # noqa: F401

revision = "0017_brd_completion"
down_revision = "0016_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch M4: subscription grace period status
    op.execute("ALTER TYPE subscription_status ADD VALUE IF NOT EXISTS 'grace'")
    op.create_table('content_pages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=60), nullable=False),
    sa.Column('title_en', sa.String(length=200), nullable=False),
    sa.Column('title_ar', sa.String(length=200), nullable=True),
    sa.Column('body_en', sa.Text(), nullable=False),
    sa.Column('body_ar', sa.Text(), nullable=True),
    sa.Column('version', sa.String(length=20), nullable=False),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('content_pages_pkey')),
    sa.UniqueConstraint('slug', name=op.f('content_pages_slug_key'))
    )
    op.create_table('ui_translations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_text', sa.Text(), nullable=False),
    sa.Column('text_ar', sa.Text(), nullable=False),
    sa.Column('context', sa.String(length=60), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('ui_translations_pkey')),
    sa.UniqueConstraint('source_text', name=op.f('ui_translations_source_text_key'))
    )
    op.create_table('data_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('reference', sa.String(length=30), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=True),
    sa.Column('request_type', sa.Enum('access', 'correction', 'deletion', 'restriction', 'objection', name='data_request_type'), nullable=False),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('open', 'in_progress', 'completed', 'rejected', name='data_request_status'), nullable=False),
    sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('handled_by_user_id', sa.UUID(), nullable=True),
    sa.Column('handled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('data_requests_company_id_fkey')),
    sa.ForeignKeyConstraint(['handled_by_user_id'], ['users.id'], name=op.f('data_requests_handled_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('data_requests_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('data_requests_pkey')),
    sa.UniqueConstraint('reference', name=op.f('data_requests_reference_key'))
    )
    op.create_index(op.f('ix_data_requests_user_id'), 'data_requests', ['user_id'], unique=False)
    op.create_table('lab_partner_terms',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lab_company_id', sa.UUID(), nullable=False),
    sa.Column('accreditation_body', sa.String(length=120), nullable=True),
    sa.Column('accreditation_number', sa.String(length=80), nullable=True),
    sa.Column('accreditation_valid_until', sa.Date(), nullable=True),
    sa.Column('accreditation_scope', sa.Text(), nullable=True),
    sa.Column('fee_sar', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('turnaround_days', sa.Integer(), nullable=True),
    sa.Column('is_accepting_requests', sa.Boolean(), nullable=False),
    sa.Column('is_preferred', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['lab_company_id'], ['companies.id'], name=op.f('lab_partner_terms_lab_company_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('lab_partner_terms_pkey')),
    sa.UniqueConstraint('lab_company_id', name=op.f('lab_partner_terms_lab_company_id_key'))
    )
    op.create_table('subscription_charges',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('reference', sa.String(length=30), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('subscription_id', sa.UUID(), nullable=True),
    sa.Column('tier', sa.String(length=20), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=True),
    sa.Column('amount_sar', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('vat_amount_sar', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total_sar', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('payment_reference', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('subscription_charges_company_id_fkey')),
    sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], name=op.f('subscription_charges_subscription_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('subscription_charges_pkey')),
    sa.UniqueConstraint('reference', name=op.f('subscription_charges_reference_key'))
    )
    op.create_index(op.f('ix_subscription_charges_company_id'), 'subscription_charges', ['company_id'], unique=False)
    op.create_table('disputes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('reference', sa.String(length=30), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('raised_by_party', sa.String(length=10), nullable=False),
    sa.Column('raised_by_company_id', sa.UUID(), nullable=False),
    sa.Column('raised_by_user_id', sa.UUID(), nullable=True),
    sa.Column('category', sa.String(length=30), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('desired_outcome', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('open', 'under_review', 'awaiting_info', 'resolved', 'withdrawn', name='dispute_status'), nullable=False),
    sa.Column('order_status_before', sa.String(length=30), nullable=False),
    sa.Column('assigned_admin_id', sa.UUID(), nullable=True),
    sa.Column('ruling', sa.Enum('buyer', 'seller', name='dispute_ruling'), nullable=True),
    sa.Column('decision_text', sa.Text(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decided_by_user_id', sa.UUID(), nullable=True),
    sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['assigned_admin_id'], ['users.id'], name=op.f('disputes_assigned_admin_id_fkey')),
    sa.ForeignKeyConstraint(['decided_by_user_id'], ['users.id'], name=op.f('disputes_decided_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('disputes_order_id_fkey')),
    sa.ForeignKeyConstraint(['raised_by_company_id'], ['companies.id'], name=op.f('disputes_raised_by_company_id_fkey')),
    sa.ForeignKeyConstraint(['raised_by_user_id'], ['users.id'], name=op.f('disputes_raised_by_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('disputes_pkey')),
    sa.UniqueConstraint('reference', name=op.f('disputes_reference_key'))
    )
    op.create_index(op.f('ix_disputes_order_id'), 'disputes', ['order_id'], unique=False)
    op.create_table('dispute_corrections',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('dispute_id', sa.UUID(), nullable=False),
    sa.Column('previous_ruling', sa.String(length=10), nullable=True),
    sa.Column('new_ruling', sa.String(length=10), nullable=True),
    sa.Column('previous_text', sa.Text(), nullable=True),
    sa.Column('new_text', sa.Text(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('corrected_by_user_id', sa.UUID(), nullable=False),
    sa.Column('corrected_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['corrected_by_user_id'], ['users.id'], name=op.f('dispute_corrections_corrected_by_user_id_fkey')),
    sa.ForeignKeyConstraint(['dispute_id'], ['disputes.id'], name=op.f('dispute_corrections_dispute_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('dispute_corrections_pkey'))
    )
    op.create_index(op.f('ix_dispute_corrections_dispute_id'), 'dispute_corrections', ['dispute_id'], unique=False)
    op.create_table('dispute_messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('dispute_id', sa.UUID(), nullable=False),
    sa.Column('author_user_id', sa.UUID(), nullable=True),
    sa.Column('author_party', sa.String(length=10), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('is_internal', sa.Boolean(), nullable=False),
    sa.Column('attachment_path', sa.String(length=255), nullable=True),
    sa.Column('attachment_name', sa.String(length=255), nullable=True),
    sa.Column('attachment_hash', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], name=op.f('dispute_messages_author_user_id_fkey')),
    sa.ForeignKeyConstraint(['dispute_id'], ['disputes.id'], name=op.f('dispute_messages_dispute_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('dispute_messages_pkey'))
    )
    op.create_index(op.f('ix_dispute_messages_dispute_id'), 'dispute_messages', ['dispute_id'], unique=False)
    op.add_column('certifications', sa.Column('renewal_of_id', sa.UUID(), nullable=True))
    op.add_column('certifications', sa.Column('is_expedited', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key(op.f('certifications_renewal_of_id_fkey'), 'certifications', 'certifications', ['renewal_of_id'], ['id'])
    op.add_column('order_documents', sa.Column('title', sa.String(length=200), nullable=True))
    op.add_column('order_documents', sa.Column('original_filename', sa.String(length=255), nullable=True))
    op.add_column('order_documents', sa.Column('mime_type', sa.String(length=80), nullable=True))
    op.add_column('order_documents', sa.Column('file_size', sa.Integer(), nullable=True))
    op.add_column('order_documents', sa.Column('is_generated', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('order_documents', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('completed_via_dispute', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('orders', sa.Column('invoice_number', sa.String(length=30), nullable=True))
    op.add_column('orders', sa.Column('invoiced_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(op.f('orders_invoice_number_key'), 'orders', ['invoice_number'])
    op.add_column('products', sa.Column('suspended_reason', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('status_before_suspension', sa.String(length=30), nullable=True))
    op.add_column('quotations', sa.Column('revision_no', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('rfqs', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('rfqs', sa.Column('cancel_reason', sa.Text(), nullable=True))
    op.add_column('subscriptions', sa.Column('expiry_notified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('changed_by_user_id', sa.UUID(), nullable=True))
    op.add_column('subscriptions', sa.Column('change_note', sa.String(length=255), nullable=True))
    op.create_foreign_key(op.f('subscriptions_changed_by_user_id_fkey'), 'subscriptions', 'users', ['changed_by_user_id'], ['id'])
    op.add_column('users', sa.Column('admin_role', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('privacy_consent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('privacy_consent_version', sa.String(length=20), nullable=True))
    op.add_column('verification_requests', sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('verification_requests', sa.Column('testing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('verification_requests', sa.Column('is_priority', sa.Boolean(), nullable=False, server_default=sa.false()))

    # --- data ---
    # Batch Q1: every existing administrator becomes a super admin (no loss of access).
    op.execute("UPDATE users SET admin_role = 'super_admin' WHERE role = 'admin' AND admin_role IS NULL")
    # Batch R1: the TEST ENVIRONMENT banner is now off by default — drop any stored override.
    op.execute("DELETE FROM system_settings WHERE key = 'dev_mode_banner'")


def downgrade() -> None:
    op.drop_column('verification_requests', 'is_priority')
    op.drop_column('verification_requests', 'testing_started_at')
    op.drop_column('verification_requests', 'scheduled_at')
    op.drop_column('users', 'privacy_consent_version')
    op.drop_column('users', 'privacy_consent_at')
    op.drop_column('users', 'admin_role')
    op.drop_constraint(op.f('subscriptions_changed_by_user_id_fkey'), 'subscriptions', type_='foreignkey')
    op.drop_column('subscriptions', 'change_note')
    op.drop_column('subscriptions', 'changed_by_user_id')
    op.drop_column('subscriptions', 'expiry_notified_at')
    op.drop_column('rfqs', 'cancel_reason')
    op.drop_column('rfqs', 'cancelled_at')
    op.drop_column('quotations', 'revision_no')
    op.drop_column('products', 'status_before_suspension')
    op.drop_column('products', 'suspended_reason')
    op.drop_constraint(op.f('orders_invoice_number_key'), 'orders', type_='unique')
    op.drop_column('orders', 'invoiced_at')
    op.drop_column('orders', 'invoice_number')
    op.drop_column('orders', 'completed_via_dispute')
    op.drop_column('order_documents', 'notes')
    op.drop_column('order_documents', 'is_generated')
    op.drop_column('order_documents', 'file_size')
    op.drop_column('order_documents', 'mime_type')
    op.drop_column('order_documents', 'original_filename')
    op.drop_column('order_documents', 'title')
    op.drop_constraint(op.f('certifications_renewal_of_id_fkey'), 'certifications', type_='foreignkey')
    op.drop_column('certifications', 'is_expedited')
    op.drop_column('certifications', 'renewal_of_id')
    op.drop_index(op.f('ix_dispute_messages_dispute_id'), table_name='dispute_messages')
    op.drop_table('dispute_messages')
    op.drop_index(op.f('ix_dispute_corrections_dispute_id'), table_name='dispute_corrections')
    op.drop_table('dispute_corrections')
    op.drop_index(op.f('ix_disputes_order_id'), table_name='disputes')
    op.drop_table('disputes')
    op.drop_index(op.f('ix_subscription_charges_company_id'), table_name='subscription_charges')
    op.drop_table('subscription_charges')
    op.drop_table('lab_partner_terms')
    op.drop_index(op.f('ix_data_requests_user_id'), table_name='data_requests')
    op.drop_table('data_requests')
    op.drop_table('ui_translations')
    op.drop_table('content_pages')
    for enum_name in ("dispute_ruling", "dispute_status", "data_request_status", "data_request_type"):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
