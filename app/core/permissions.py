"""
app/core/permissions.py
"""
from fastapi import Depends
from app.core.auth import get_current_user_required
from app.core.exceptions import CompanyNotApprovedException, ForbiddenException
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

    ADMIN always passes, regardless of which portal(s) the route
    restricts to. BRD §6.8 gives admins full visibility across every
    company/product/order/dispute — the same principle extends
    naturally to just *viewing* another portal's dashboard, so an
    admin can open /seller/dashboard, /buyer/dashboard, /lab/dashboard
    directly without needing a second login. Non-admin users are
    unaffected: still gated by role match + company approval exactly
    as before.
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
