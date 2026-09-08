"""
app/core/portal_nav.py

Builds the context every "real app" page (seller/buyer/lab/admin
dashboards, notifications) needs to render layouts/base.html correctly:
portal_label, nav_items (drives partials/sidebar.html), current_user
(drives both sidebar.html and partials/header.html's profile dropdown).

One place for this instead of duplicating a near-identical dict in
five different route files — when a portal's nav grows in a later
batch (Batch 5's listings, etc.), it changes here once.

`portal_role` is the portal being VIEWED — each route passes its own
role explicitly (e.g. seller/dashboard/routes.py always passes
UserRole.SELLER). This is deliberately separate from `user.role`
(who's actually logged in), because an admin can now open any portal
dashboard directly (see core/permissions.py's require_active_portal).
When those two differ, the sidebar/nav shown match the portal being
PREVIEWED, while current_user still reflects who's really logged in —
and `is_admin_preview` tells the template to show a banner so it's
never ambiguous which mode you're in.
"""
from app.models.user import User, UserRole

_NAV_ITEMS = {
    UserRole.SELLER: [
        {"icon": "bi-columns-gap", "label": "Dashboard", "url": "/seller/dashboard"},
    ],
    UserRole.BUYER: [
        {"icon": "bi-columns-gap", "label": "Dashboard", "url": "/buyer/dashboard"},
    ],
    UserRole.LAB: [
        {"icon": "bi-columns-gap", "label": "Dashboard", "url": "/lab/dashboard"},
    ],
    UserRole.ADMIN: [
        {"icon": "bi-inbox", "label": "Pending Approvals", "url": "/admin/approvals"},
    ],
}

_UPCOMING_ITEMS = {
    UserRole.SELLER: [
        {"icon": "bi-diagram-3", "label": "My Listings"},
        {"icon": "bi-eyedropper", "label": "Verification Requests"},
        {"icon": "bi-inbox", "label": "RFQ Inbox"},
        {"icon": "bi-box-seam", "label": "Orders"},
    ],
    UserRole.BUYER: [
        {"icon": "bi-search", "label": "Browse Minerals"},
        {"icon": "bi-file-earmark-text", "label": "My RFQs"},
        {"icon": "bi-tags", "label": "Quotations"},
        {"icon": "bi-box-seam", "label": "Orders"},
    ],
    UserRole.LAB: [
        {"icon": "bi-eyedropper", "label": "Verification Requests"},
        {"icon": "bi-patch-check", "label": "Certificates Issued"},
    ],
    UserRole.ADMIN: [
        {"icon": "bi-flag", "label": "Disputes"},
        {"icon": "bi-shield-check", "label": "Mineral Passports"},
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

    nav_items = [
        {**item, "active": item["url"] == active_path} for item in _NAV_ITEMS[portal_role]
    ]

    context = {
        "portal_label": _PORTAL_LABEL[portal_role],
        "lang": user.preferred_language,
        "nav_items": nav_items,
        "upcoming_items": _UPCOMING_ITEMS[portal_role],
        "current_user": {
            "full_name": user.full_name,
            "company_name": user.company.company_name if user.company else "Platform Administration",
            "avatar_url": "/static/img/logo-512.png",
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
