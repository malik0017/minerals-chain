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
    """BRD §6.11 — applies to seller/buyer companies. Labs: see open question in BRD, left nullable."""
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
    # Mine licence (sellers) or lab accreditation number (labs). Buyers: nullable.
    license_or_accreditation_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

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
