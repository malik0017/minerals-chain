"""
app/services/verification_service.py
"""
import hashlib
import json
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.certification import (Certification, CertificationResult, CertificationScope, CertificationStatus, CertificationType)
from app.models.lab_partner import LabPartnerTerms
from app.models.company import ApprovalStatus, Company, CompanyRole
from app.models.notification import Notification
from app.models.product import Product, ProductStatus
from app.models.user import User
from app.models.verification import VerificationRequest, VerificationStatus
from app.services import notification_service
from app.repositories import audit_log_repository, certification_repository, notification_repository, verification_repository
from app.services import certification_service, spec_service
from app.core.system_settings import get_setting
from app.services.reference_service import next_reference

_ACTIVE_STATUSES = (VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED, VerificationStatus.TESTING_IN_PROGRESS)
_EDITABLE_PRODUCT_STATUSES = (ProductStatus.DRAFT, ProductStatus.FAILED_VERIFICATION)


class VerificationActionError(ValueError):
    """Raised for any invalid verification action. Routes catch this
    and show the message."""
    pass


def _notify_company_users(db: Session, target_company: Company, *, type_: str, title: str, body: str,
                           action_url: str | None = None, **params) -> None:
    # Batch M6: bilingual, deep-linked — see services/notification_service.py
    notification_service.notify_company(db, target_company, type_, title, body, action_url=action_url, **params)


def request_verification(db: Session, product: Product, lab_company: Company, requester: User) -> VerificationRequest:
    if product.status not in _EDITABLE_PRODUCT_STATUSES:
        raise VerificationActionError(
            f"This listing can't be submitted for verification while it's {product.status.value.replace('_', ' ')}."
        )
    if lab_company.role != CompanyRole.LAB or lab_company.status != ApprovalStatus.APPROVED:
        raise VerificationActionError("The selected lab isn't available for verification requests.")
    if verification_repository.has_active_request(db, product.id):
        raise VerificationActionError("This listing already has a verification request in progress.")
    # Batch M2: lab partner terms (BRD §6.3 "an approved partner laboratory")
    terms = db.query(LabPartnerTerms).filter_by(lab_company_id=lab_company.id).first()
    if terms is not None and not terms.is_accepting_requests:
        raise VerificationActionError("This lab is not accepting new requests at the moment.")
    if terms is not None and not terms.accreditation_current:
        raise VerificationActionError("This lab's accreditation has expired — choose another lab.")
    # Batch M3: declared specification before testing (admin setting)
    if get_setting(db, "require_specs_for_verification") and not spec_service.product_rows(db, product):
        raise VerificationActionError("Add the product specification (parameters and ranges) before requesting verification.")

    request = VerificationRequest(
        product_id=product.id,
        lab_company_id=lab_company.id,
        status=VerificationStatus.REQUESTED,
        # Batch J (Schema V1 lab_requests): reference + fee snapshot.
        request_reference=next_reference(db, "verification"),
        fee_sar=(terms.fee_sar if terms is not None and terms.fee_sar is not None
                 else get_setting(db, "lab_verification_fee_sar")),
        # BRD §6.11: premium sellers get priority verification
        is_priority=_is_premium(product.seller_company),
    )
    verification_repository.create(db, request)

    product.status = ProductStatus.UNDER_VERIFICATION

    _notify_company_users(
        db, lab_company,
        type_="verification_requested",
        title="New verification request",
        body=f"A seller has requested verification for a {product.mineral_type} listing.",
        action_url=f"/lab/verification-requests/{request.id}", mineral=product.mineral_type,
    )

    db.commit()
    db.refresh(request)
    return request


def _is_premium(company: Company) -> bool:
    tier = getattr(company, "subscription_tier", None)
    return bool(tier) and getattr(tier, "value", str(tier)) == "premium"


def get_owned_lab_request(db: Session, request_id: uuid.UUID, lab_company_id: uuid.UUID) -> VerificationRequest:
    request = verification_repository.get_by_id(db, request_id)
    if request is None or request.lab_company_id != lab_company_id:
        raise VerificationActionError("Verification request not found.")
    return request


def issue_certificate(
    db: Session, request: VerificationRequest, lab_user: User, tested_parameters_notes: str
) -> Certification:
    if request.status not in _ACTIVE_STATUSES:
        raise VerificationActionError(f"This request is already {request.status.value}.")

    certification = certification_service.create_lab_certificate(db, request, lab_user, tested_parameters_notes)

    request.status = VerificationStatus.COMPLETED
    request.product.status = ProductStatus.VERIFIED

    _notify_company_users(
        db, request.product.seller_company,
        type_="verification_passed",
        title="Verification passed",
        body=f"Your {request.product.mineral_type} listing has been verified. Certificate {certification.certificate_number} issued.",
        action_url=f"/seller/listings/{request.product_id}", mineral=request.product.mineral_type,
        certificate=certification.certificate_number,
    )

    db.commit()
    db.refresh(certification)
    return certification


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
        action_url=f"/seller/listings/{request.product_id}", mineral=request.product.mineral_type, reason=rejection_reason,
    )

    db.commit()
    db.refresh(request)
    return request


def _audit(db, user: User, action: str, vr: VerificationRequest, details: str = "") -> None:
    audit_log_repository.create(db, AuditLog(actor_user_id=user.id, action=action, target_type="verification_request",
                                             target_id=vr.id, details=f"{vr.request_reference}: {details}"[:500]))


def schedule_sample(db: Session, vr: VerificationRequest, lab_user: User, collection_date: str,
                    field_officer: str, sample_id: str = "") -> None:
    if vr.status not in (VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED):
        raise VerificationActionError("Sample collection can only be scheduled before testing starts.")
    try:
        when = date.fromisoformat(collection_date)
    except (TypeError, ValueError):
        raise VerificationActionError("Choose a collection date.")
    if not (field_officer or "").strip():
        raise VerificationActionError("Enter the field officer who will collect the sample.")
    vr.collection_date = when
    vr.field_officer = field_officer.strip()[:120]
    vr.sample_id = (sample_id or "").strip()[:60] or vr.sample_id or f"S-{secrets.token_hex(3).upper()}"
    vr.scheduled_at = datetime.now(timezone.utc)
    vr.status = VerificationStatus.SAMPLE_SCHEDULED
    _notify_company_users(db, vr.product.seller_company, type_="verification_scheduled",
                          title="Sample collection scheduled",
                          body=f"The lab scheduled sample collection for your {vr.product.mineral_type} listing on {when}.",
                          action_url=f"/seller/listings/{vr.product_id}", mineral=vr.product.mineral_type, date=str(when))
    _audit(db, lab_user, "verification_scheduled", vr, f"{when} · {vr.field_officer} · {vr.sample_id}")
    db.commit()


def start_testing(db: Session, vr: VerificationRequest, lab_user: User) -> None:
    if vr.status != VerificationStatus.SAMPLE_SCHEDULED:
        raise VerificationActionError("Schedule and collect the sample before starting testing.")
    vr.status = VerificationStatus.TESTING_IN_PROGRESS
    vr.testing_started_at = datetime.now(timezone.utc)
    _notify_company_users(db, vr.product.seller_company, type_="verification_testing", title="Testing started",
                          body=f"The lab started testing the sample of your {vr.product.mineral_type} listing.",
                          action_url=f"/seller/listings/{vr.product_id}", mineral=vr.product.mineral_type)
    _audit(db, lab_user, "verification_testing", vr)
    db.commit()


def _n(v) -> str:
    return "" if v is None else format(Decimal(v).normalize(), "f")


def coa_fingerprint(cert: Certification) -> str:
    payload = {
        "number": cert.certificate_number, "request": str(cert.verification_request_id),
        "lab": str(cert.issuing_company_id), "subject": str(cert.subject_company_id),
        "issued": str(cert.issue_date), "pass": cert.all_parameters_pass,
        "results": sorted([[r.parameter, _n(r.required_min), _n(r.required_max), _n(r.measured_value),
                            r.unit or "", bool(r.passed)] for r in cert.results]),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def record_results(db: Session, vr: VerificationRequest, lab_user: User, rows: list[dict],
                   analyst_name: str, notes: str = "") -> Certification:
    if vr.status != VerificationStatus.TESTING_IN_PROGRESS:
        raise VerificationActionError("Start testing before entering results.")
    if not rows:
        raise VerificationActionError("Enter at least one tested parameter.")
    if not (analyst_name or "").strip():
        raise VerificationActionError("Enter the analyst's name.")
    now = datetime.now(timezone.utc)
    results, failing = [], []
    for r in rows:
        try:
            measured = Decimal(str(r.get("measured", "")).strip())
        except (InvalidOperation, ValueError):
            raise VerificationActionError(f"{r['parameter']}: enter the measured value.")
        ok = spec_service.judge(measured, r.get("min"), r.get("max"))
        if not ok:
            failing.append(f"{r['parameter']} {measured} (required {spec_service.range_label(r.get('min'), r.get('max'), r.get('unit'))})")
        results.append(CertificationResult(parameter=r["parameter"][:80], required_min=r.get("min"), required_max=r.get("max"),
                                           measured_value=measured, unit=r.get("unit"), test_method=r.get("test_method"),
                                           passed=ok))
    all_pass = not failing
    product = vr.product
    cert = Certification(
        cert_type=CertificationType.LAB_CERTIFICATE, name="Certificate of Analysis",
        subject_company_id=product.seller_company_id, issuing_company_id=vr.lab_company_id,
        verification_request_id=vr.id, issued_by_user_id=lab_user.id,
        certificate_number=next_reference(db, "coa"),
        notes=(notes or "").strip() or None, issue_date=date.today(),
        status=CertificationStatus.APPROVED if all_pass else CertificationStatus.REJECTED,
        rejection_reason=None if all_pass else "; ".join(failing),
        reviewed_at=now, signed_off_at=now, signed_off_by_user_id=lab_user.id,
        analyst_name=analyst_name.strip()[:120], sample_collected_at=vr.collection_date, test_completed_at=date.today(),
        all_parameters_pass=all_pass, fee_sar=vr.fee_sar, batch_id=vr.batch_id,
    )
    coa_days = get_setting(db, "coa_validity_days")
    if all_pass and coa_days:
        cert.expiry_date = date.today() + timedelta(days=coa_days)
    cert.results = results
    certification_repository.create(db, cert)
    certification_repository.create_scope(db, CertificationScope(certification_id=cert.id, product_id=product.id))
    db.flush()
    cert.file_hash = coa_fingerprint(cert)
    vr.completed_at = now
    if all_pass:
        vr.status = VerificationStatus.COMPLETED
        product.status = ProductStatus.VERIFIED
        _notify_company_users(db, product.seller_company, type_="verification_passed", title="Verification passed",
                              body=f"Your {product.mineral_type} listing passed all tested parameters. Certificate {cert.certificate_number} issued.",
                              action_url=f"/seller/listings/{product.id}", mineral=product.mineral_type,
                              certificate=cert.certificate_number)
    else:
        vr.status = VerificationStatus.FAILED
        vr.rejection_reason = "Out of specification: " + "; ".join(failing)
        product.status = ProductStatus.FAILED_VERIFICATION
        _notify_company_users(db, product.seller_company, type_="verification_failed", title="Verification not passed",
                              body=f"Your {product.mineral_type} listing did not pass. {vr.rejection_reason}",
                              action_url=f"/seller/listings/{product.id}", mineral=product.mineral_type,
                              reason=vr.rejection_reason)
    _audit(db, lab_user, "verification_results", vr, f"{'PASS' if all_pass else 'FAIL'} · {cert.certificate_number}")
    db.commit()
    db.refresh(cert)
    return cert

