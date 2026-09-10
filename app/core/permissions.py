"""
app/core/permissions.py
"""
from fastapi import Depends
from app.core.auth import get_current_user_required
from app.core.exceptions import AdminRedirectException, CompanyNotApprovedException, ForbiddenException
from app.models.company import ApprovalStatus
from app.models.user import User, UserRole


def require_portal(*allowed_roles: UserRole):
    def _dependency(user: User = Depends(get_current_user_required)) -> User:
        if user.role not in allowed_roles:
            raise ForbiddenException()
        return user

    return _dependency


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

    Batch 8: an admin hitting this no longer gets a blunt 403 — they're
    redirected to /admin/companies (filtered to sellers), which shows
    the same underlying data from the admin oversight angle instead.
    See AdminRedirectException's docstring for why this is different
    from a general admin bypass.
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
    Phase 2 Batch 2: gates buyer RFQ management (create/view own
    RFQs). Same admin-redirect treatment as require_seller_company —
    admin gets sent to /admin/companies?role=buyer instead of a 403,
    since there's no "which buyer" default for admin to act as.
    """
    if user.role == UserRole.ADMIN:
        raise AdminRedirectException("admin_companies_list", query="role=buyer")
    if user.role != UserRole.BUYER:
        raise ForbiddenException()
    if user.company is None or user.company.status != ApprovalStatus.APPROVED:
        raise CompanyNotApprovedException()
    return user
