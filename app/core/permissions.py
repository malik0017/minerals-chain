"""
app/core/permissions.py
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_required
from app.core.system_settings import get_setting
from app.database.base import get_db
from app.core.exceptions import AdminRedirectException, CompanyNotApprovedException, ForbiddenException
from app.models.company import ApprovalStatus
from app.models.user import User, UserRole


def require_portal(*allowed_roles: UserRole):
    def _dependency(user: User = Depends(get_current_user_required), db: Session = Depends(get_db)) -> User:
        if user.role not in allowed_roles:
            raise ForbiddenException()
        _enforce_admin_2fa(user, db)
        return user

    return _dependency


def _enforce_admin_2fa(user: User, db: Session) -> None:
    if user.role == UserRole.ADMIN and not user.totp_enabled and get_setting(db, "enforce_admin_2fa"):
        raise AdminRedirectException("my_profile_2fa_setup")


def require_approved_company(user: User = Depends(get_current_user_required)) -> User:
    if user.role == UserRole.ADMIN:
        return user
    if user.company is None or user.company.status != ApprovalStatus.APPROVED:
        raise ForbiddenException()
    return user


def require_active_portal(*allowed_roles: UserRole):
    """
    Role + approval gate for the real portal dashboards.

    """
    def _dependency(user: User = Depends(get_current_user_required)) -> User:
        if user.role == UserRole.ADMIN:
            return user
        if user.role not in allowed_roles:
            raise ForbiddenException()
        if user.company is None or user.company.status != ApprovalStatus.APPROVED:
            raise CompanyNotApprovedException()
        return user

    return _dependency


def require_seller_company(user: User = Depends(get_current_user_required)) -> User:
    """
    Gates seller listing management (create/edit/view own products).
    """
    if user.role == UserRole.ADMIN:
        raise AdminRedirectException("admin_companies_list", query="role=seller")
    if user.role != UserRole.SELLER:
        raise ForbiddenException()
    if user.company is None or user.company.status != ApprovalStatus.APPROVED:
        raise CompanyNotApprovedException()
    return user


def require_lab_company(user: User = Depends(get_current_user_required)) -> User:
    """Gates lab verification-request management. Same admin-redirect
    treatment as require_seller_company — see its docstring."""
    if user.role == UserRole.ADMIN:
        raise AdminRedirectException("admin_companies_list", query="role=lab")
    if user.role != UserRole.LAB:
        raise ForbiddenException()
    if user.company is None or user.company.status != ApprovalStatus.APPROVED:
        raise CompanyNotApprovedException()
    return user


def require_buyer_company(user: User = Depends(get_current_user_required)) -> User:
    """ 
    Gates buyer RFQ management (create/view own
    RFQs). """
    if user.role == UserRole.ADMIN:
        raise AdminRedirectException("admin_companies_list", query="role=buyer")
    if user.role != UserRole.BUYER:
        raise ForbiddenException()
    if user.company is None or user.company.status != ApprovalStatus.APPROVED:
        raise CompanyNotApprovedException()
    return user


ADMIN_ROLES = {
    "super_admin": {"label": "Super administrator", "areas": {"*"}},
    "operations": {"label": "Operations", "areas": {
        "dashboard", "approvals", "companies", "users_view", "passports", "master_data", "products",
        "rfqs", "orders", "disputes", "labs", "subscriptions", "reports"}},
    "finance": {"label": "Finance", "areas": {
        "dashboard", "companies", "orders", "finance", "subscriptions", "reports"}},
    "compliance": {"label": "Compliance / DPO", "areas": {
        "dashboard", "companies", "users_view", "orders", "disputes", "audit", "data_requests", "reports"}},
    "support": {"label": "Support", "areas": {
        "dashboard", "companies", "users_view", "users", "data_requests", "orders"}},
}


def admin_can(user: User, area: str) -> bool:
    if user.role != UserRole.ADMIN:
        return False
    role = ADMIN_ROLES.get(user.admin_role or "super_admin", ADMIN_ROLES["super_admin"])
    areas = role["areas"]
    if "*" in areas or area in areas:
        return True
    return area == "users_view" and "users" in areas


def require_admin(area: str):
    """Admin-only route gate for one permission area (see ADMIN_ROLES)."""
    def _dependency(user: User = Depends(get_current_user_required), db: Session = Depends(get_db)) -> User:
        if user.role != UserRole.ADMIN:
            raise ForbiddenException()
        _enforce_admin_2fa(user, db)
        if not admin_can(user, area):
            raise ForbiddenException()
        return user

    return _dependency
