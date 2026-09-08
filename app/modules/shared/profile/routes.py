"""
app/modules/shared/profile/routes.py

Replaces the /my-profile stub in main.py. Works for any logged-in
user — admin, seller, buyer, lab — since it's about the account
itself, not a portal-specific feature. Uses the viewer's own role as
portal_role (build_portal_context) so the sidebar still shows their
normal nav.
"""
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_required
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User
from app.schemas.profile import PasswordChangeRequest, ProfileUpdateRequest
from app.services.avatar_service import AvatarActionError, remove_avatar, save_avatar
from app.services.profile_service import ProfileActionError, change_password, update_profile

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
):
    context = build_portal_context(user, user.role, active_path=None)
    context.update({
        "profile_errors": [profile_errors] if profile_errors else [],
        "password_errors": [password_errors] if password_errors else [],
        "password_success": password_success,
        "avatar_errors": [avatar_errors] if avatar_errors else [],
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
