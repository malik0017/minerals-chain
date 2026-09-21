"""
app/modules/auth/routes.py

Registration (Batch B) is now three POST endpoints against the same
page: /register/send-otp and /register/verify-otp (both preserve every
already-typed field via the same raw_form re-population pattern used
for validation errors elsewhere in this app) gate the real
/register submission behind proving control of the email address.
Neither of those two ever touches the database — no user or company
exists until the final POST succeeds.

One HTML limitation worth knowing: file inputs can never be
pre-filled for security reasons, so if someone attaches CR/licence
documents and THEN clicks "Send code" (which reloads the page), those
selections are lost and need reattaching. The template puts the email
verification step ahead of the document uploads specifically to steer
people away from hitting this in normal top-to-bottom use.
"""
import hashlib
import uuid

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.auth import SESSION_COOKIE_NAME, get_current_user_optional, get_current_user_required
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
LANG_COOKIE_NAME = "mc_lang"  # Batch C — shared with modules/shared/routes.py's /language/set


def _anon_lang(request: Request) -> str:
    """Batch C: for pages with no logged-in user yet (login, register,
    the 2FA code step) there's no User.preferred_language to read —
    falls back to the mc_lang cookie set by /language/set, or "en" if
    that's never been set either."""
    lang = request.cookies.get(LANG_COOKIE_NAME, "en")
    return lang if lang in SUPPORTED_LANGUAGES else "en"


def _client_ip(request: Request) -> str:
    """Batch G: identity key for IP-based rate limiting. Trusts
    X-Forwarded-For's first hop when present (this app expects to sit
    behind a reverse proxy/load balancer in any real deployment —
    request.client.host would otherwise always be the proxy's own
    address, collapsing every real visitor into one rate-limit bucket),
    falling back to request.client.host directly for local/dev."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

# Common calling codes for a Saudi-market platform — Saudi Arabia first/default,
# then the rest of the GCC, then a handful of other frequent trading partners.
# Not exhaustive by design; easy to extend without touching any logic.
#
# Hotfix: "flag" used to be a raw flag emoji (e.g. "\U0001F1F8\U0001F1E6"),
# rendered inside a native <select><option>. That works on macOS/Linux, but
# on Windows the OS-drawn <select> list box has no colored-emoji glyph for
# regional-indicator flag sequences, so it fell back to showing the two bare
# letters ("SA", "AE", ...) instead of a flag - exactly the "text codes, not
# flags" complaint. Native <select> can't host an <img> at all, on any OS.
# Fix: keep "flag" (still used as a plain-text fallback/accessible label),
# add "iso2" so the template can render a real flagcdn.com <img> flag in a
# custom Bootstrap dropdown (see auth/register.html) instead of a native
# <select>, which renders identically everywhere.
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
    """
    Task #7: the admin audit-log viewer needs to show *who logged in and
    when*, not just the "approve/reject/reset password" admin-action
    entries Batch G already recorded. Logged for every real, completed
    login (password-only and the second half of the 2FA flow) - not for
    the auto-login right after registration, which is a distinct event
    already implied by the account's own "Registered" timestamp.
    """
    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=user.id,
            action="login",
            target_type="user",
            target_id=user.id,
        ),
    )
    db.commit()


def _set_session_cookie(response: RedirectResponse, user: User) -> None:
    token = create_access_token(user_id=str(user.id))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=settings.cookie_secure_effective,  # Batch G — see COOKIE_SECURE in core/config.py
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

    # Task #4: admin-controlled per-role registration toggle + dev-mode
    # OTP bypass. Reading the settings row here (rather than duplicating
    # this fetch in every route below) means every render of this page —
    # first load or any re-render after a POST — reflects the current
    # admin settings without extra plumbing.
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
        # True only when the CURRENTLY TYPED email matches what was verified —
        # changing the email after verifying correctly un-verifies it. When
        # OTP verification isn't required (admin dev-mode toggle), treat
        # every email as already "verified" so the form doesn't block on it.
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

    # Batch G: caps how many codes can be requested for one email address —
    # protects a real inbox from being spammed and keeps the platform's
    # email volume/cost bounded against a scripted client hammering this
    # endpoint. Keyed by email, not IP, since the actual cost (an email
    # sent) is per-email regardless of how many different IPs request it.
    rate_limit.check(
        "otp_send", email_clean,
        max_attempts=settings.OTP_SEND_RATE_LIMIT_MAX,
        window_seconds=settings.OTP_SEND_RATE_LIMIT_WINDOW_SECONDS,
    )

    token = request_otp(email_clean)
    context = _register_context(request, raw_form, [], db)
    # The cookie we're about to set on the response isn't visible via
    # request.cookies until the NEXT request — override here so this
    # same render already shows the code-entry step instead of looking
    # like nothing happened.
    context["otp_sent"] = True
    response = templates.TemplateResponse(request, "auth/register.html", context)
    response.set_cookie(
        key=REG_OTP_PENDING_COOKIE, value=token, httponly=True, samesite="lax", max_age=10 * 60,
        secure=settings.cookie_secure_effective,
    )
    response.delete_cookie(REG_EMAIL_VERIFIED_COOKIE)  # sending a new code un-verifies any previous email
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
    # Batch G: caps how many codes can be TRIED against one pending OTP
    # token — without this, a 6-digit code (1,000,000 possibilities) could
    # be brute-forced well inside its 10-minute lifetime. Keyed by a hash
    # of the token itself (never the raw token, which is also a live
    # session-ish credential — no reason to also use it as a rate-limit
    # dictionary key/log value) so each registration attempt gets its own
    # attempt budget rather than sharing one across every visitor.
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
    # Same reasoning as register_send_otp_route above — the verified
    # cookie we're about to set isn't visible in request.cookies yet
    # on this same render, so set the state explicitly.
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
):
    raw_form = _raw_form_from(
        role, company_name, cr_number, license_or_accreditation_number,
        contact_phone_country_code, contact_phone_number, full_name, email,
    )

    def _error(messages: list[str], status_code: int = 422):
        context = _register_context(request, raw_form, messages, db)
        return templates.TemplateResponse(request, "auth/register.html", context, status_code=status_code)

    platform_settings = platform_settings_repository.get_settings(db)

    # --- Task #4: per-role registration toggle — checked first, since a
    # disabled role shouldn't even get to the (possibly also-bypassed) OTP
    # check below. Re-validated here server-side, not just hidden/disabled
    # in the template, since the template state is never trusted alone. ---
    settings_field = _ROLE_SETTINGS_FIELD.get(role)
    if settings_field is not None and not getattr(platform_settings, settings_field):
        return _error(["Registration for this role is currently disabled. Contact the platform administrator."], status_code=403)

    # --- Batch B: email OTP gate — checked before anything else. Task #4:
    # skipped entirely when the admin has turned off require_email_otp
    # (dev/staging convenience). ---
    if platform_settings.require_email_otp:
        verified_token = request.cookies.get(REG_EMAIL_VERIFIED_COOKIE)
        verified_email = decode_email_verified_token(verified_token) if verified_token else None
        if verified_email is None or verified_email != email.strip().lower():
            return _error(["Please verify your email address before submitting."], status_code=400)

    # --- Batch B: phone digits-only check on the number part, combined with the country code ---
    digits_only = contact_phone_number.strip()
    if not digits_only.isdigit():
        return _error(["Phone number must contain digits only (no spaces or symbols)."])
    combined_phone = f"{contact_phone_country_code} {digits_only}"

    # --- Batch B: CR + licence documents — mandatory, validated before the row is ever touched ---
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
    # Batch G: IP-wide throttle, complementary to the existing per-account
    # lockout in auth_service.py (LOCKOUT_THRESHOLD) — that one protects a
    # single account from repeated guesses; this one caps how many login
    # attempts (against ANY account) one IP can make, which the per-account
    # lockout does nothing for. Counts even a doomed-to-fail attempt, which
    # is what makes it a real limit.
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
    # Batch G: a 6-digit TOTP code has a small enough space that it needs
    # its own throttle — the pending-2FA token is only 5 minutes, but
    # without this an automated client could still try many codes in that
    # window.
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
    return response


@router.get("/home", name="home")
def home(request: Request, user: User = Depends(get_current_user_required)):
    if user.role == UserRole.ADMIN:
        # Batch 3: admins land on the approvals queue instead of the
        # generic dashboard-test page.
        return RedirectResponse(url=request.url_for("admin_approvals_list"), status_code=303)

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
