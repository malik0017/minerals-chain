"""
Every model MUST be imported here. Alembic's env.py imports this module
so that Base.metadata knows about all tables when autogenerating a
migration. A model that isn't imported here is invisible to `alembic
revision --autogenerate` and will silently be left out of migrations.

Batch 1: Company, User.
Batch 3: Notification, AuditLog.
Batch 5: Product.
Batch 6: VerificationRequest, Certificate.
Batch 9: MineralPassport.
Phase 2 Batch 2: RFQ.
Phase 2 Batch 3: Quotation.
Phase 2 Batch 4: Order — closes out Phase 2.
Batch A (schema evolution): Certificate + MineralPassport REPLACED by
  Certification + CertificationScope (see models/certification.py's
  docstring for why). Subscription added (real history table,
  Company.subscription_tier is now just a cache — see its docstring).
Batch I (ERP Master Data): md_* master tables, ProductMaster, Batch/Lot.
Batch J (Schema V1 alignment): ProductSpec, CertificationResult, RFQSpec,
  RevealLog, OrderDocument, SettlementFee, DocumentSequence.
Batch K (Admin Control Center): SystemSetting.

File-per-table convention: master-data tables are grouped by family
(md_classification, md_units, md_quality, md_locations, md_commercial,
md_product) because each family is only ever read/edited together and the
generic admin registry treats them uniformly — one file per ~20 tiny
tables would add noise, not clarity.

Later batches will add: Dispute, Invoice — add each new model's
import here as it's created.
"""
from app.models.company import Company  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.verification import VerificationRequest  # noqa: F401
from app.models.certification import Certification, CertificationScope  # noqa: F401
from app.models.subscription import Subscription  # noqa: F401
from app.models.rfq import RFQ  # noqa: F401
from app.models.quotation import Quotation  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.platform_settings import PlatformSettings  # noqa: F401

# --- Batch I: ERP master data ---
from app.models.md_commercial import (  # noqa: F401
    Application, CustomerSegment, HSCode, Incoterm, PaymentTerm, SubscriptionPlan,
)
from app.models.md_units import PackagingType, ParticleSize, UnitOfMeasure  # noqa: F401
from app.models.md_classification import Grade, MineralGroup, MineralType  # noqa: F401
from app.models.md_quality import QualityParameter, QualitySpecification, TestMethod  # noqa: F401
from app.models.md_locations import MineSource, Region, Warehouse, WarehouseBin  # noqa: F401
from app.models.md_product import ProductMaster, ProductMasterApplication, ProductMasterPackaging  # noqa: F401
from app.models.batch import Batch, BatchQualityResult  # noqa: F401

# --- Batch J: Schema V1 alignment ---
from app.models.product_spec import ProductSpec  # noqa: F401
from app.models.certification import CertificationResult  # noqa: F401
from app.models.rfq import RFQSpec  # noqa: F401
from app.models.order import OrderDocument, RevealLog, SettlementFee  # noqa: F401
from app.models.document_sequence import DocumentSequence  # noqa: F401

# --- Batch K: Admin Control Center ---
from app.models.system_setting import SystemSetting  # noqa: F401

# --- Batch R1: localization ---
from app.models.ui_translation import UITranslation  # noqa: F401

# --- Batch Q1 / M1 / M2 / M4 ---
from app.models.content_page import ContentPage  # noqa: F401
from app.models.data_request import DataRequest  # noqa: F401
from app.models.dispute import Dispute, DisputeCorrection, DisputeMessage  # noqa: F401
from app.models.lab_partner import LabPartnerTerms  # noqa: F401
from app.models.subscription import SubscriptionCharge  # noqa: F401
