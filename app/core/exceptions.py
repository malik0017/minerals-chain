"""
app/core/exceptions.py

"""


class NotAuthenticatedException(Exception):
    pass

class ForbiddenException(Exception):
    pass


class CompanyNotApprovedException(Exception):
    pass


class AdminRedirectException(Exception):
    """
    Batch 8: raised instead of ForbiddenException when an admin hits a
    company-scoped page (seller listings, lab verification management)
    that has no per-admin equivalent of its own. A raw 403 here reads
    as "the app is broken" rather than "this page doesn't apply to
    you" — admin already has an equivalent view (the /admin/companies
    oversight pages) that shows the same underlying data, so redirect
    there instead of dead-ending.

    Only used for pages that are inherently scoped to ONE company's
    data with no sensible "which company" default — not a general
    admin-bypass mechanism. Regular /admin/* pages still use
    require_portal(UserRole.ADMIN) and a real ForbiddenException for
    non-admins, unchanged.
    """
    def __init__(self, redirect_route_name: str, query: str | None = None):
        self.redirect_route_name = redirect_route_name
        self.query = query
