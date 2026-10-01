"""
app/modules/auth/routes.py
"""
import hashlib
import uuid

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.auth import IMPERSONATOR_COOKIE_NAME, SESSION_COOKIE_NAME, get_current_user_optional, get_current_user_required
from app.core.config import settings
from app.core.localization import SUPPORTED_LANGUAGES
from app.core import rate_limit
from app.core.security import (
    create_access_token,
    create_pending_2fa_token,
    decode_email_verified_token,
    decode_pending_2fa_token,
)
from app.database.base import get_db
from app.models.audit_log import AuditLog
from app.models.company import ApprovalStatus
from app.models.user import User, UserRole
from app.repositories import audit_log_repository, platform_settings_repository, user_repository
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthenticationError, RegistrationError, authenticate_user, register_new_company_user
from app.services.document_upload_service import DocumentUploadError, validate_document
from app.services.registration_otp_service import RegistrationOTPError, request_otp, verify_otp
from app.services.two_factor_service import verify_code

router = APIRouter()
from app.core.templates import templates

PENDING_2FA_COOKIE_NAME = "mc_2fa_pending"
REG_OTP_PENDING_COOKIE = "mc_reg_otp_pending"
REG_EMAIL_VERIFIED_COOKIE = "mc_reg_email_verified"
LANG_COOKIE_NAME = "mc_lang"  


def _anon_lang(request: Request) -> str:
    lang = request.cookies.get(LANG_COOKIE_NAME, "en")
    return lang if lang in SUPPORTED_LANGUAGES else "en"


def _client_ip(request: Request) -> str:
    from app.core.client_ip import client_ip
    return client_ip(request)

PHONE_COUNTRY_CODES = [
    {"flag": "🇸🇦", "iso2": "sa", "name": "Saudi Arabia", "dial": "+966"},
    {"flag": "🇦🇪", "iso2": "ae", "name": "UAE", "dial": "+971"},
    {"flag": "🇰🇼", "iso2": "kw", "name": "Kuwait", "dial": "+965"},
    {"flag": "🇶🇦", "iso2": "qa", "name": "Qatar", "dial": "+974"},
    {"flag": "🇧🇭", "iso2": "bh", "name": "Bahrain", "dial": "+973"},
    {"flag": "🇴🇲", "iso2": "om", "name": "Oman", "dial": "+968"},
    {"flag": "🇪🇬", "iso2": "eg", "name": "Egypt", "dial": "+20"},
    {"flag": "🇯🇴", "iso2": "jo", "name": "Jordan", "dial": "+962"},
    {"flag": "🇵🇰", "iso2": "pk", "name": "Pakistan", "dial": "+92"},
    {"flag": "🇮🇳", "iso2": "in", "name": "India", "dial": "+91"},
    {"flag": "🇬🇧", "iso2": "gb", "name": "United Kingdom", "dial": "+44"},
    {"flag": "🇺🇸", "iso2": "us", "name": "United States", "dial": "+1"},
]


def _log_login(db: Session, user: User) -> None:
   
    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=user.id,
            action="login",
            target_type="user",
            target_id=user.id,
        ),
    )
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()


def _set_session_cookie(response: RedirectResponse, user: User) -> None:
    token = create_access_token(user_id=str(user.id))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=settings.cookie_secure_effective,  
    )


_ROLE_SETTINGS_FIELD = {
    "seller": "registration_enabled_seller",
    "buyer": "registration_enabled_buyer",
    "lab": "registration_enabled_lab",
}


def _register_context(request: Request, raw_form: dict, errors: list[str], db: Session) -> dict:
    """Shared by GET /register and every POST that re-renders the same
    page — computes the OTP/verification state from cookies so the
    template can show the right step."""
    pending_token = request.cookies.get(REG_OTP_PENDING_COOKIE)
    verified_token = request.cookies.get(REG_EMAIL_VERIFIED_COOKIE)
    verified_email = decode_email_verified_token(verified_token) if verified_token else None
    platform_settings = platform_settings_repository.get_settings(db)
    disabled_roles = {
        role for role, field in _ROLE_SETTINGS_FIELD.items() if not getattr(platform_settings, field)
    }
    otp_required = platform_settings.require_email_otp
    default_role = next((r for r in ("seller", "buyer", "lab") if r not in disabled_roles), "seller")

    return {
        "errors": errors,
        "form": raw_form,
        "phone_country_codes": PHONE_COUNTRY_CODES,
        "otp_sent": bool(pending_token),
        "verified_email": verified_email,
        "email_is_verified": not otp_required or (
            verified_email is not None and verified_email == (raw_form.get("email") or "").strip().lower()
        ),
        "otp_required": otp_required,
        "disabled_roles": disabled_roles,
        "default_role": default_role,
        "lang": _anon_lang(request),
    }


@router.get("/register", name="register_form")
def register_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    if user is not None:
        return RedirectResponse(url=request.url_for("home"), status_code=303)
    context = _register_context(request, {}, [], db)
    return templates.TemplateResponse(request, "auth/register.html", context)


def _raw_form_from(
    role, company_name, cr_number, license_or_accreditation_number,
    contact_phone_country_code, contact_phone_number, full_name, email,
) -> dict:
    return {
        "role": role, "company_name": company_name, "cr_number": cr_number,
        "license_or_accreditation_number": license_or_accreditation_number,
        "contact_phone_country_code": contact_phone_country_code,
        "contact_phone_number": contact_phone_number,
        "full_name": full_name, "email": email,
    }


@router.post("/register/send-otp", name="register_send_otp")
def register_send_otp_route(
    request: Request,
    db: Session = Depends(get_db),
    role: str = Form(""),
    company_name: str = Form(""),
    cr_number: str = Form(""),
    license_or_accreditation_number: str = Form(""),
    contact_phone_country_code: str = Form("+966"),
    contact_phone_number: str = Form(""),
    full_name: str = Form(""),
    email: str = Form(""),
):
    raw_form = _raw_form_from(
        role, company_name, cr_number, license_or_accreditation_number,
        contact_phone_country_code, contact_phone_number, full_name, email,
    )

    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        context = _register_context(request, raw_form, ["Enter a valid email address before requesting a code."], db)
        return templates.TemplateResponse(request, "auth/register.html", context, status_code=422)

    rate_limit.check(
        "otp_send", email_clean,
        max_attempts=settings.OTP_SEND_RATE_LIMIT_MAX,
        window_seconds=settings.OTP_SEND_RATE_LIMIT_WINDOW_SECONDS,
    )

    token = request_otp(email_clean)
    context = _register_context(request, raw_form, [], db)
    context["otp_sent"] = True
    response = templates.TemplateResponse(request, "auth/register.html", context)
    response.set_cookie(
        key=REG_OTP_PENDING_COOKIE, value=token, httponly=True, samesite="lax", max_age=10 * 60,
        secure=settings.cookie_secure_effective,
    )
    response.delete_cookie(REG_EMAIL_VERIFIED_COOKIE)  
    return response


@router.post("/register/verify-otp", name="register_verify_otp")
def register_verify_otp_route(
    request: Request,
    db: Session = Depends(get_db),
    role: str = Form(""),
    company_name: str = Form(""),
    cr_number: str = Form(""),
    license_or_accreditation_number: str = Form(""),
    contact_phone_country_code: str = Form("+966"),
    contact_phone_number: str = Form(""),
    full_name: str = Form(""),
    email: str = Form(""),
    otp_code: str = Form(""),
):
    raw_form = _raw_form_from(
        role, company_name, cr_number, license_or_accreditation_number,
        contact_phone_country_code, contact_phone_number, full_name, email,
    )

    pending_token = request.cookies.get(REG_OTP_PENDING_COOKIE)
    token_key = hashlib.sha256((pending_token or "no-token").encode()).hexdigest()
    rate_limit.check(
        "otp_verify", token_key,
        max_attempts=settings.OTP_VERIFY_RATE_LIMIT_MAX,
        window_seconds=settings.OTP_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )

    try:
        verified_token = verify_otp(pending_token, otp_code)
    except RegistrationOTPError as exc:
        context = _register_context(request, raw_form, [str(exc)], db)
        return templates.TemplateResponse(request, "auth/register.html", context, status_code=400)

    context = _register_context(request, raw_form, [], db)
    context["otp_sent"] = False
    context["email_is_verified"] = True
    context["verified_email"] = email.strip().lower()
    response = templates.TemplateResponse(request, "auth/register.html", context)
    response.set_cookie(
        key=REG_EMAIL_VERIFIED_COOKIE, value=verified_token, httponly=True, samesite="lax", max_age=30 * 60,
        secure=settings.cookie_secure_effective,
    )
    response.delete_cookie(REG_OTP_PENDING_COOKIE)
    return response


def _privacy_version(db: Session) -> str:
    from app.models.content_page import ContentPage
    page = db.query(ContentPage).filter(ContentPage.slug == "privacy").first()
    return page.version if page else "1.0"


@router.post("/register", name="register_submit")
async def register_submit(
    request: Request,
    db: Session = Depends(get_db),
    role: str = Form(...),
    company_name: str = Form(...),
    cr_number: str = Form(...),
    license_or_accreditation_number: str = Form(""),
    contact_phone_country_code: str = Form("+966"),
    contact_phone_number: str = Form(""),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    cr_document: UploadFile = None,
    license_document: UploadFile = None,
    privacy_consent: str = Form(""),
):
    raw_form = _raw_form_from(
        role, company_name, cr_number, license_or_accreditation_number,
        contact_phone_country_code, contact_phone_number, full_name, email,
    )

    def _error(messages: list[str], status_code: int = 422):
        context = _register_context(request, raw_form, messages, db)
        return templates.TemplateResponse(request, "auth/register.html", context, status_code=status_code)

    platform_settings = platform_settings_repository.get_settings(db)
    settings_field = _ROLE_SETTINGS_FIELD.get(role)
    if settings_field is not None and not getattr(platform_settings, settings_field):
        return _error(["Registration for this role is currently disabled. Contact the platform administrator."], status_code=403)

    if platform_settings.require_email_otp:
        verified_token = request.cookies.get(REG_EMAIL_VERIFIED_COOKIE)
        verified_email = decode_email_verified_token(verified_token) if verified_token else None
        if verified_email is None or verified_email != email.strip().lower():
            return _error(["Please verify your email address before submitting."], status_code=400)

    if not privacy_consent:
        return _error(["Please read and accept the Privacy Notice to register."])

    digits_only = contact_phone_number.strip()
    if not digits_only.isdigit():
        return _error(["Phone number must contain digits only (no spaces or symbols)."])
    combined_phone = f"{contact_phone_country_code} {digits_only}"

    try:
        cr_contents = await cr_document.read() if cr_document else b""
        cr_ext = validate_document(cr_document, cr_contents, field_label="CR document")
        license_contents = await license_document.read() if license_document else b""
        license_ext = validate_document(license_document, license_contents, field_label="Licence/accreditation document")
    except DocumentUploadError as exc:
        return _error([str(exc)])

    try:
        payload = RegisterRequest(
            role=role,
            company_name=company_name,
            cr_number=cr_number,
            license_or_accreditation_number=license_or_accreditation_number,
            contact_phone=combined_phone,
            full_name=full_name,
            email=email,
            password=password,
            confirm_password=confirm_password,
        )
        user = register_new_company_user(
            db, payload,
            cr_document_contents=cr_contents, cr_document_ext=cr_ext,
            license_document_contents=license_contents, license_document_ext=license_ext,
            consent_version=_privacy_version(db),
        )
    except ValidationError as exc:
        errors = [err["msg"] for err in exc.errors()]
        return _error(errors)
    except RegistrationError as exc:
        db.rollback()
        return _error([str(exc)], status_code=400)

    response = RedirectResponse(url=request.url_for("home"), status_code=303)
    _set_session_cookie(response, user)
    response.delete_cookie(REG_EMAIL_VERIFIED_COOKIE)
    response.delete_cookie(REG_OTP_PENDING_COOKIE)
    return response


@router.get("/login", name="login_form")
def login_form(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user is not None:
        return RedirectResponse(url=request.url_for("home"), status_code=303)
    return templates.TemplateResponse(request, "auth/login.html", {"error": None, "email": "", "lang": _anon_lang(request)})


@router.post("/login", name="login_submit")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    rate_limit.check(
        "login", _client_ip(request),
        max_attempts=settings.LOGIN_RATE_LIMIT_MAX,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )

    try:
        payload = LoginRequest(email=email, password=password)
        user = authenticate_user(db, payload.email, payload.password)
    except ValidationError:
        return templates.TemplateResponse(
            request, "auth/login.html", {"error": "Incorrect email or password.", "email": email, "lang": _anon_lang(request)}, status_code=400
        )
    except AuthenticationError as exc:
        return templates.TemplateResponse(
            request, "auth/login.html", {"error": str(exc), "email": email, "lang": _anon_lang(request)}, status_code=400
        )

    if user.totp_enabled:
        token = create_pending_2fa_token(user_id=str(user.id))
        response = RedirectResponse(url=request.url_for("login_2fa_form"), status_code=303)
        response.set_cookie(
            key=PENDING_2FA_COOKIE_NAME, value=token, httponly=True, samesite="lax", max_age=5 * 60,
            secure=settings.cookie_secure_effective,
        )
        return response

    response = RedirectResponse(url=request.url_for("home"), status_code=303)
    _set_session_cookie(response, user)
    _log_login(db, user)
    rate_limit.reset("login", _client_ip(request))
    return response


def _pending_2fa_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(PENDING_2FA_COOKIE_NAME)
    if not token:
        return None
    user_id = decode_pending_2fa_token(token)
    if not user_id:
        return None
    try:
        return user_repository.get_by_id(db, uuid.UUID(user_id))
    except ValueError:
        return None


@router.get("/login/2fa", name="login_2fa_form")
def login_2fa_form(request: Request, db: Session = Depends(get_db)):
    user = _pending_2fa_user(request, db)
    if user is None or not user.totp_enabled:
        return RedirectResponse(url=request.url_for("login_form"), status_code=303)
    return templates.TemplateResponse(request, "auth/login_2fa.html", {"error": None, "lang": _anon_lang(request)})


@router.post("/login/2fa", name="login_2fa_submit")
def login_2fa_submit(request: Request, db: Session = Depends(get_db), code: str = Form(...)):

    rate_limit.check(
        "login_2fa", _client_ip(request),
        max_attempts=settings.LOGIN_RATE_LIMIT_MAX,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )

    user = _pending_2fa_user(request, db)
    if user is None or not user.totp_enabled:
        return RedirectResponse(url=request.url_for("login_form"), status_code=303)

    if not verify_code(user.totp_secret, code):
        return templates.TemplateResponse(
            request, "auth/login_2fa.html", {"error": "That code didn't match. Try again.", "lang": _anon_lang(request)}, status_code=400
        )

    response = RedirectResponse(url=request.url_for("home"), status_code=303)
    _set_session_cookie(response, user)
    _log_login(db, user)
    response.delete_cookie(PENDING_2FA_COOKIE_NAME)
    rate_limit.reset("login_2fa", _client_ip(request))
    return response


@router.get("/logout", name="logout")
def logout(request: Request):
    response = RedirectResponse(url=request.url_for("login_form"), status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(PENDING_2FA_COOKIE_NAME)
    response.delete_cookie(IMPERSONATOR_COOKIE_NAME)
    return response


@router.get("/home", name="home")
def home(request: Request, user: User = Depends(get_current_user_required)):
    if user.role == UserRole.ADMIN:
        return RedirectResponse(url=request.url_for("admin_control_center"), status_code=303)

    if user.company is not None and user.company.status != ApprovalStatus.APPROVED:
        return templates.TemplateResponse(
            request,
            "auth/account_status.html",
            {
                "status": user.company.status.value,
                "rejection_reason": user.company.rejection_reason,
                "company_name": user.company.company_name,
                "lang": user.preferred_language,
            },
        )

    portal_route = {
        UserRole.SELLER: "seller_dashboard",
        UserRole.BUYER: "buyer_dashboard",
        UserRole.LAB: "lab_dashboard",
    }[user.role]
    return RedirectResponse(url=request.url_for(portal_route), status_code=303)
