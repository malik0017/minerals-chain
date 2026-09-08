"""
Every model MUST be imported here. Alembic's env.py imports this module
so that Base.metadata knows about all tables when autogenerating a
migration. A model that isn't imported here is invisible to `alembic
revision --autogenerate` and will silently be left out of migrations.

Batch 1: Company, User.
Batch 3: Notification, AuditLog.
Later batches will add: Product, VerificationRequest, Certificate,
MineralPassport, RFQ, Quotation, Order, Dispute, Invoice — add each
new model's import here as it's created.
"""
from app.models.company import Company  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
