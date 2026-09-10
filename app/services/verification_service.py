"""
app/services/verification_service.py
"""
import secrets
import uuid

from sqlalchemy.orm import Session

from app.models.certificate import Certificate
from app.models.company import ApprovalStatus, Company, CompanyRole
from app.models.notification import Notification
from app.models.product import Product, ProductStatus
from app.models.user import User
from app.models.verification import VerificationRequest, VerificationStatus
from app.repositories import certificate_repository, notification_repository, verification_repository

_ACTIVE_STATUSES = (VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED, VerificationStatus.TESTING_IN_PROGRESS)
_EDITABLE_PRODUCT_STATUSES = (ProductStatus.DRAFT, ProductStatus.FAILED_VERIFICATION)


class VerificationActionError(ValueError):
    """Raised for any invalid verification action. Routes catch this
    and show the message."""
    pass


def _notify_company_users(db: Session, company: Company, *, type_: str, title: str, body: str) -> None:
    for user in company.users:
        notification_repository.create(
            db, Notification(user_id=user.id, type=type_, title=title, body=body)
        )


def request_verification(db: Session, product: Product, lab_company: Company, requester: User) -> VerificationRequest:
    if product.status not in _EDITABLE_PRODUCT_STATUSES:
        raise VerificationActionError(
            f"This listing can't be submitted for verification while it's {product.status.value.replace('_', ' ')}."
        )
    if lab_company.role != CompanyRole.LAB or lab_company.status != ApprovalStatus.APPROVED:
        raise VerificationActionError("The selected lab isn't available for verification requests.")
    if verification_repository.has_active_request(db, product.id):
        raise VerificationActionError("This listing already has a verification request in progress.")

    request = VerificationRequest(
        product_id=product.id,
        lab_company_id=lab_company.id,
        status=VerificationStatus.REQUESTED,
    )
    verification_repository.create(db, request)

    product.status = ProductStatus.UNDER_VERIFICATION

    _notify_company_users(
        db, lab_company,
        type_="verification_requested",
        title="New verification request",
        body=f"{requester.company.company_name} has requested verification for a {product.mineral_type} listing.",
    )

    db.commit()
    db.refresh(request)
    return request


def get_owned_lab_request(db: Session, request_id: uuid.UUID, lab_company_id: uuid.UUID) -> VerificationRequest:
    request = verification_repository.get_by_id(db, request_id)
    if request is None or request.lab_company_id != lab_company_id:
        raise VerificationActionError("Verification request not found.")
    return request


def issue_certificate(
    db: Session, request: VerificationRequest, lab_user: User, tested_parameters_notes: str
) -> Certificate:
    if request.status not in _ACTIVE_STATUSES:
        raise VerificationActionError(f"This request is already {request.status.value}.")

    certificate = Certificate(
        verification_request_id=request.id,
        product_id=request.product_id,
        lab_company_id=request.lab_company_id,
        issued_by_user_id=lab_user.id,
        certificate_number=f"COA-{secrets.token_hex(4).upper()}",
        tested_parameters_notes=tested_parameters_notes,
    )
    certificate_repository.create(db, certificate)

    request.status = VerificationStatus.COMPLETED
    request.product.status = ProductStatus.VERIFIED

    _notify_company_users(
        db, request.product.seller_company,
        type_="verification_passed",
        title="Verification passed",
        body=f"Your {request.product.mineral_type} listing has been verified. Certificate {certificate.certificate_number} issued.",
    )

    db.commit()
    db.refresh(certificate)
    return certificate


def reject_verification(db: Session, request: VerificationRequest, lab_user: User, rejection_reason: str) -> VerificationRequest:
    if request.status not in _ACTIVE_STATUSES:
        raise VerificationActionError(f"This request is already {request.status.value}.")

    request.status = VerificationStatus.FAILED
    request.rejection_reason = rejection_reason
    request.product.status = ProductStatus.FAILED_VERIFICATION

    _notify_company_users(
        db, request.product.seller_company,
        type_="verification_failed",
        title="Verification not passed",
        body=f"Your {request.product.mineral_type} listing did not pass verification. Reason: {rejection_reason}",
    )

    db.commit()
    db.refresh(request)
    return request
