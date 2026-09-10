"""
app/modules/shared/profile/routes.py
"""
from fastapi import APIRouter, Depends, Form, Request, Response, UploadFile
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_required
from app.core.portal_nav import build_portal_context
from app.core.security import verify_password
from app.database.base import get_db
from app.models.user import User
from app.schemas.profile import PasswordChangeRequest, ProfileUpdateRequest
from app.schemas.two_factor import TotpConfirmRequest, TotpDisableRequest
from app.services.avatar_service import AvatarActionError, remove_avatar, save_avatar
from app.services.profile_service import ProfileActionError, change_password, update_profile
from app.services.two_factor_service import (
    TwoFactorActionError,
    confirm_enrollment,
    disable_totp,
    get_provisioning_uri,
    start_enrollment,
    verify_code,
)

router = APIRouter(tags=["profile"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/my-profile", name="my_profile")
def profile_page(
    request: Request,
    user: User = Depends(get_current_user_required),
    profile_errors: str | None = None,
    password_errors: str | None = None,
    password_success: bool = False,
    avatar_errors: str | None = None,
    two_factor_errors: str | None = None,
):
    context = build_portal_context(user, user.role, active_path=None)
    context.update({
        "profile_errors": [profile_errors] if profile_errors else [],
        "password_errors": [password_errors] if password_errors else [],
        "password_success": password_success,
        "avatar_errors": [avatar_errors] if avatar_errors else [],
        "two_factor_errors": [two_factor_errors] if two_factor_errors else [],
    })
    return templates.TemplateResponse(request, "shared/profile.html", context)


@router.post("/my-profile", name="my_profile_update")
def profile_update(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
    full_name: str = Form(...),
):
    try:
        payload = ProfileUpdateRequest(full_name=full_name)
        update_profile(db, user, payload)
    except ValidationError as exc:
        return profile_page(request, user, profile_errors=exc.errors()[0]["msg"])
    return profile_page(request, user)


@router.post("/my-profile/password", name="my_profile_change_password")
def profile_change_password(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    try:
        payload = PasswordChangeRequest(
            current_password=current_password, new_password=new_password, confirm_password=confirm_password
        )
        change_password(db, user, payload)
    except (ValidationError, ProfileActionError) as exc:
        db.rollback()
        msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return profile_page(request, user, password_errors=msg)
    return profile_page(request, user, password_success=True)


@router.post("/my-profile/avatar", name="my_profile_avatar_upload")
async def profile_avatar_upload(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
    avatar: UploadFile = None,
):
    if avatar is None or not avatar.filename:
        return profile_page(request, user, avatar_errors="Choose an image to upload.")
    try:
        contents = await avatar.read()
        save_avatar(db, user, avatar, contents)
    except AvatarActionError as exc:
        db.rollback()
        return profile_page(request, user, avatar_errors=str(exc))
    return profile_page(request, user)


@router.post("/my-profile/avatar/remove", name="my_profile_avatar_remove")
def profile_avatar_remove(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
):
    remove_avatar(db, user)
    return profile_page(request, user)


# --- Batch 10: two-factor authentication ---

@router.get("/my-profile/2fa/setup", name="my_profile_2fa_setup")
def two_factor_setup(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
    error: str | None = None,
):
    if not user.totp_enabled:
        # Fresh secret every time this page loads — see
        # two_factor_service.start_enrollment()'s docstring for why.
        start_enrollment(db, user)
    context = build_portal_context(user, user.role, active_path=None)
    context["error"] = error
    return templates.TemplateResponse(request, "shared/two_factor_setup.html", context)


@router.get("/my-profile/2fa/qr.png", name="my_profile_2fa_qr")
def two_factor_qr(user: User = Depends(get_current_user_required)):
    import io
    import qrcode

    uri = get_provisioning_uri(user)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.post("/my-profile/2fa/confirm", name="my_profile_2fa_confirm")
def two_factor_confirm(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
    code: str = Form(...),
):
    try:
        payload = TotpConfirmRequest(code=code)
        confirm_enrollment(db, user, payload.code)
    except (ValidationError, TwoFactorActionError) as exc:
        db.rollback()
        msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        context = build_portal_context(user, user.role, active_path=None)
        context["error"] = msg
        return templates.TemplateResponse(request, "shared/two_factor_setup.html", context, status_code=400)
    return profile_page(request, user)


@router.post("/my-profile/2fa/disable", name="my_profile_2fa_disable")
def two_factor_disable(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
    current_password: str = Form(...),
    code: str = Form(...),
):
    try:
        payload = TotpDisableRequest(current_password=current_password, code=code)
        if not verify_password(payload.current_password, user.hashed_password):
            raise TwoFactorActionError("Current password is incorrect.")
        if not verify_code(user.totp_secret, payload.code):
            raise TwoFactorActionError("That code didn't match.")
        disable_totp(db, user)
    except (ValidationError, TwoFactorActionError) as exc:
        db.rollback()
        msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return profile_page(request, user, two_factor_errors=msg)
    return profile_page(request, user)
