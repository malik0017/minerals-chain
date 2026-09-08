"""
app/core/portal_nav.py
"""
from app.models.user import User, UserRole

_NAV_ITEMS = {
    UserRole.SELLER: [
        {"icon": "bi-columns-gap", "label": "Dashboard", "url": "/seller/dashboard"},
        {"icon": "bi-diagram-3", "label": "My Listings", "url": "/seller/listings"},
    ],
    UserRole.BUYER: [
        {"icon": "bi-columns-gap", "label": "Dashboard", "url": "/buyer/dashboard"},
    ],
    UserRole.LAB: [
        {"icon": "bi-columns-gap", "label": "Dashboard", "url": "/lab/dashboard"},
        {"icon": "bi-eyedropper", "label": "Verification Requests", "url": "/lab/verification-requests"},
    ],
    UserRole.ADMIN: [
        {"icon": "bi-inbox", "label": "Pending Approvals", "url": "/admin/approvals"},
        {"icon": "bi-building", "label": "All Companies", "url": "/admin/companies"},
        {"icon": "bi-people", "label": "Users", "url": "/admin/users"},
        {"icon": "bi-shield-check", "label": "Mineral Passports", "url": "/admin/passports"},
    ],
}

_UPCOMING_ITEMS = {
    UserRole.SELLER: [
        {"icon": "bi-inbox", "label": "RFQ Inbox"},
        {"icon": "bi-box-seam", "label": "Orders"},
    ],
    UserRole.BUYER: [
        {"icon": "bi-search", "label": "Browse Minerals"},
        {"icon": "bi-file-earmark-text", "label": "My RFQs"},
        {"icon": "bi-tags", "label": "Quotations"},
        {"icon": "bi-box-seam", "label": "Orders"},
    ],
    UserRole.LAB: [],
    UserRole.ADMIN: [
        {"icon": "bi-flag", "label": "Disputes"},
        {"icon": "bi-graph-up", "label": "Reports"},
    ],
}

_PORTAL_LABEL = {
    UserRole.SELLER: "Seller Portal",
    UserRole.BUYER: "Buyer Portal",
    UserRole.LAB: "Lab Portal",
    UserRole.ADMIN: "Admin Portal",
}

# Real, working links admin sees on every portal page — lets an admin
# jump straight to any portal's dashboard without logging out/in again.
_ADMIN_PREVIEW_LINKS = [
    {"icon": "bi-inbox", "label": "Pending Approvals", "url": "/admin/approvals"},
    {"icon": "bi-columns-gap", "label": "Seller Dashboard", "url": "/seller/dashboard"},
    {"icon": "bi-columns-gap", "label": "Buyer Dashboard", "url": "/buyer/dashboard"},
    {"icon": "bi-columns-gap", "label": "Lab Dashboard", "url": "/lab/dashboard"},
]


def build_portal_context(user: User, portal_role: UserRole, active_path: str | None = None) -> dict:
    """
    portal_role: which portal's page is being rendered (drives nav_items/
    portal_label/upcoming_items). Pass the route's own role explicitly —
    e.g. seller/dashboard/routes.py always passes UserRole.SELLER, even
    when an admin is the one viewing it.

    active_path: the current request path (e.g. request.url.path) —
    used to mark the matching nav item active. Pass None (e.g. from
    the shared /notifications page) and nothing gets marked active.
    """
    is_admin_preview = user.role == UserRole.ADMIN and portal_role != UserRole.ADMIN

    # Batch 7: when admin is previewing another portal, the header
    # subtitle now says so explicitly ("Admin Portal · Previewing
    # Lab") instead of just "Lab Portal" — the preview banner already
    # explained this, but the header itself looking identical to a
    # real lab session was confusing on its own, out of banner-reading
    # context (e.g. a screenshot of just the header).
    if is_admin_preview:
        portal_label = f"Admin Portal · Previewing {_PORTAL_LABEL[portal_role]}"
    else:
        portal_label = _PORTAL_LABEL[portal_role]

    nav_items = [
        {**item, "active": item["url"] == active_path} for item in _NAV_ITEMS[portal_role]
    ]

    context = {
        "portal_label": portal_label,
        "lang": user.preferred_language,
        "nav_items": nav_items,
        "upcoming_items": _UPCOMING_ITEMS[portal_role],
        "current_user": {
            "full_name": user.full_name,
            "email": user.email,
            "company_name": user.company.company_name if user.company else "Platform Administration",
            "avatar_url": f"/static/uploads/avatars/{user.avatar_filename}" if user.avatar_filename else "/static/img/logo-512.png",
        },
        "notifications": [],
        "unread_notifications": 0,
        "is_admin_preview": is_admin_preview,
    }

    # Every real page an admin can see also gets quick links to every
    # portal — the "view all portals without logging in again" ask.
    if user.role == UserRole.ADMIN:
        context["admin_preview_links"] = [
            {**item, "active": item["url"] == active_path} for item in _ADMIN_PREVIEW_LINKS
        ]

    return context
