"""
app/models/company.py

"""
import enum
import uuid
from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

class CompanyRole(str, enum.Enum):
    SELLER = "seller"
    BUYER = "buyer"
    LAB = "lab"

class ApprovalStatus(str, enum.Enum):
    """
    BRD §6.1: every new registration starts PENDING; no account is
    functionally active until an admin approves it.
    """
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"   # admin can suspend a previously-approved company (§6.8)

class SubscriptionTier(str, enum.Enum):
    """BRD §6.11 — applies to seller/buyer companies. Labs: see open question in BRD, left nullable.
    Batch A: this enum is still the fast-access "what tier is this company on right now"
    cache on Company itself — but app/models/subscription.py's Subscription table is now
    the real source of truth for history/start-end dates/attributes. Keep both in sync via
    services/subscription_service.py, never write one without the other."""
    ENTRY = "entry"
    MID = "mid"
    PREMIUM = "premium"


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Identity ---
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[CompanyRole] = mapped_column(
        SAEnum(CompanyRole, name="company_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )

    # --- Legal credentials (BRD §7: mandatory before activation) ---
    cr_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # Batch B: license/accreditation number is now MANDATORY for every role, not just
    # seller/lab — per explicit direction: apply the same registration conditions
    # uniformly across buyer, seller, and lab. (Previously nullable for buyers only.)
    # A buyer's value here is whatever trade/business licence they hold, not a mine
    # licence specifically — the field's meaning is role-dependent, its presence isn't.
    license_or_accreditation_number: Mapped[str] = mapped_column(String(100), nullable=False)
    # Batch B: the two supporting documents, mandatory alongside the numbers above —
    # just the filename (matches the avatar_filename pattern), not a full path. Files
    # live in app/static/uploads/company_documents/, written by
    # services/document_upload_service.py during registration, AFTER the company row
    # exists (needs company.id for the filename) — see auth_service.py.
    cr_document_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    license_document_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Batch A: VAT Registration Number — needed for ZATCA e-invoicing (Phase 3) on every
    # invoice line, but the field belongs on the company record itself, not deferred until
    # invoicing is built. Nullable — not every registrant has one yet at signup time (a
    # newly-formed company may still be completing VAT registration with ZATCA); required
    # before an order can be invoiced is a Phase 3 enforcement point, not a registration one.
    vat_registration_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- Approval workflow (BRD §6.1) ---
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus, name="approval_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # --- Subscription (BRD §6.11) ---
    # See the SubscriptionTier docstring above — this is now a cache, not the source of truth.
    subscription_tier: Mapped[SubscriptionTier | None] = mapped_column(
        SAEnum(SubscriptionTier, name="subscription_tier", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
        default=SubscriptionTier.ENTRY,
    )

    # --- Contact ---
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- Relationships ---
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="company",
        foreign_keys="User.company_id",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Company {self.company_name} ({self.role.value}, {self.status.value})>"
