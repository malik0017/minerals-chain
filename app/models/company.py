"""
app/models/company.py

"""
import enum
import uuid
from datetime import date
from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, String, Text
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
    SUSPENDED = "suspended"   # admin can suspend a previously-approved company 

class SubscriptionTier(str, enum.Enum):
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

    cr_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    license_or_accreditation_number: Mapped[str] = mapped_column(String(100), nullable=False)
    cr_document_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    license_document_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    vat_registration_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- Approval workflow 
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus, name="approval_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # --- Subscription  ---
    subscription_tier: Mapped[SubscriptionTier | None] = mapped_column(
        SAEnum(SubscriptionTier, name="subscription_tier", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
        default=SubscriptionTier.ENTRY,
    )

    # --- Contact ---
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    company_name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    national_address: Mapped[str | None] = mapped_column(String(20), nullable=True)
    customer_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_segments.id"), nullable=True
    )
    license_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    license_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_founding_member: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subscription_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    region: Mapped["Region"] = relationship("Region")
    customer_segment: Mapped["CustomerSegment"] = relationship("CustomerSegment")

    # --- Relationships ---
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="company",
        foreign_keys="User.company_id",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Company {self.company_name} ({self.role.value}, {self.status.value})>"
