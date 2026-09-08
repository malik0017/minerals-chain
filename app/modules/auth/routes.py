"""
app/modules/auth/routes.py
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.auth import SESSION_COOKIE_NAME, get_current_user_optional, get_current_user_required
from app.core.config import settings
from app.core.security import create_access_token
from app.database.base import get_db
from app.models.company import ApprovalStatus
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthenticationError, RegistrationError, authenticate_user, register_new_company_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _set_session_cookie(response: RedirectResponse, user: User) -> None:
    token = create_access_token(user_id=str(user.id))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        # secure=True   # TODO(hardening batch): enable once served over HTTPS on AWS
    )


@router.get("/register", name="register_form")
def register_form(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user is not None:
        return RedirectResponse(url=request.url_for("home"), status_code=303)
    return templates.TemplateResponse(request, "auth/register.html", {"errors": [], "form": {}})


@router.post("/register", name="register_submit")
def register_submit(
    request: Request,
    db: Session = Depends(get_db),
    role: str = Form(...),
    company_name: str = Form(...),
    cr_number: str = Form(...),
    license_or_accreditation_number: str = Form(""),
    contact_phone: str = Form(""),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    raw_form = {
        "role": role,
        "company_name": company_name,
        "cr_number": cr_number,
        "license_or_accreditation_number": license_or_accreditation_number,
        "contact_phone": contact_phone,
        "full_name": full_name,
        "email": email,
    }

    try:
        payload = RegisterRequest(
            role=role,
            company_name=company_name,
            cr_number=cr_number,
            license_or_accreditation_number=license_or_accreditation_number or None,
            contact_phone=contact_phone or None,
            full_name=full_name,
            email=email,
            password=password,
            confirm_password=confirm_password,
        )
        user = register_new_company_user(db, payload)
    except ValidationError as exc:
        errors = [err["msg"] for err in exc.errors()]
        return templates.TemplateResponse(
            request, "auth/register.html", {"errors": errors, "form": raw_form}, status_code=422
        )
    except RegistrationError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request, "auth/register.html", {"errors": [str(exc)], "form": raw_form}, status_code=400
        )

    response = RedirectResponse(url=request.url_for("home"), status_code=303)
    _set_session_cookie(response, user)
    return response


@router.get("/login", name="login_form")
def login_form(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user is not None:
        return RedirectResponse(url=request.url_for("home"), status_code=303)
    return templates.TemplateResponse(request, "auth/login.html", {"error": None, "email": ""})


@router.post("/login", name="login_submit")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    try:
        payload = LoginRequest(email=email, password=password)
        user = authenticate_user(db, payload.email, payload.password)
    except (ValidationError, AuthenticationError):
        # Same generic message for "no such email" and "wrong password" —
        # deliberate, see AuthenticationError's docstring.
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Incorrect email or password.", "email": email},
            status_code=400,
        )

    response = RedirectResponse(url=request.url_for("home"), status_code=303)
    _set_session_cookie(response, user)
    return response


@router.get("/logout", name="logout")
def logout(request: Request):
    response = RedirectResponse(url=request.url_for("login_form"), status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
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
            },
        )

    # Batch 4: approved seller/buyer/lab users go to their real portal
    # dashboard now instead of the generic dashboard-test page.
    portal_route = {
        UserRole.SELLER: "seller_dashboard",
        UserRole.BUYER: "buyer_dashboard",
        UserRole.LAB: "lab_dashboard",
    }[user.role]
    return RedirectResponse(url=request.url_for(portal_route), status_code=303)
