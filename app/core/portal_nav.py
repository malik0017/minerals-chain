"""
app/core/portal_nav.py
"""
from app.core.localization import t
from app.models.user import User, UserRole

# Keys reference app/core/localization.py's TRANSLATIONS dict — every
# label below is a translation key now (Batch C), not literal English,
# resolved via t(key, lang) inside build_portal_context().
_NAV_ITEMS = {
    UserRole.SELLER: [
        {"icon": "bi-columns-gap", "key": "nav.dashboard", "url": "/seller/dashboard"},
        {"icon": "bi-diagram-3", "key": "nav.my_listings", "url": "/seller/listings"},
        {"icon": "bi-inbox", "key": "nav.rfq_inbox", "url": "/seller/rfq-inbox"},
        {"icon": "bi-tags", "key": "nav.my_quotations", "url": "/seller/quotations"},
        {"icon": "bi-box-seam", "key": "nav.orders", "url": "/seller/orders"},
    ],
    UserRole.BUYER: [
        {"icon": "bi-columns-gap", "key": "nav.dashboard", "url": "/buyer/dashboard"},
        {"icon": "bi-search", "key": "nav.browse_minerals", "url": "/buyer/browse"},
        {"icon": "bi-file-earmark-text", "key": "nav.my_rfqs", "url": "/buyer/rfqs"},
        {"icon": "bi-box-seam", "key": "nav.orders", "url": "/buyer/orders"},
    ],
    UserRole.LAB: [
        {"icon": "bi-columns-gap", "key": "nav.dashboard", "url": "/lab/dashboard"},
        {"icon": "bi-eyedropper", "key": "nav.verification_requests", "url": "/lab/verification-requests"},
    ],
    UserRole.ADMIN: [
        {"icon": "bi-inbox", "key": "nav.pending_approvals", "url": "/admin/approvals"},
        {"icon": "bi-building", "key": "nav.all_companies", "url": "/admin/companies"},
        {"icon": "bi-people", "key": "nav.users", "url": "/admin/users"},
        {"icon": "bi-shield-check", "key": "nav.mineral_passports", "url": "/admin/passports"},
    ],
}

_UPCOMING_ITEMS = {
    UserRole.SELLER: [],
    UserRole.BUYER: [],
    UserRole.LAB: [],
    UserRole.ADMIN: [
        {"icon": "bi-flag", "key": "nav.disputes"},
        {"icon": "bi-graph-up", "key": "nav.reports"},
    ],
}

_PORTAL_LABEL_KEY = {
    UserRole.SELLER: "portal.seller",
    UserRole.BUYER: "portal.buyer",
    UserRole.LAB: "portal.lab",
    UserRole.ADMIN: "portal.admin",
}

# Real, working links admin sees on every portal page — lets an admin
# jump straight to any portal's dashboard without logging out/in again.
_ADMIN_PREVIEW_LINKS = [
    {"icon": "bi-inbox", "key": "nav.pending_approvals", "url": "/admin/approvals"},
    {"icon": "bi-columns-gap", "key": "nav.seller_dashboard", "url": "/seller/dashboard"},
    {"icon": "bi-columns-gap", "key": "nav.buyer_dashboard", "url": "/buyer/dashboard"},
    {"icon": "bi-columns-gap", "key": "nav.lab_dashboard", "url": "/lab/dashboard"},
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
    lang = user.preferred_language

    # Batch 7: when admin is previewing another portal, the header
    # subtitle now says so explicitly ("Admin Portal · Previewing
    # Lab") instead of just "Lab Portal" — the preview banner already
    # explained this, but the header itself looking identical to a
    # real lab session was confusing on its own, out of banner-reading
    # context (e.g. a screenshot of just the header).
    if is_admin_preview:
        portal_label = f"{t('portal.admin', lang)} · {t('portal.previewing', lang)} {t(_PORTAL_LABEL_KEY[portal_role], lang)}"
    else:
        portal_label = t(_PORTAL_LABEL_KEY[portal_role], lang)

    nav_items = [
        {**item, "label": t(item["key"], lang), "active": item["url"] == active_path}
        for item in _NAV_ITEMS[portal_role]
    ]
    upcoming_items = [
        {**item, "label": t(item["key"], lang)} for item in _UPCOMING_ITEMS[portal_role]
    ]

    context = {
        "portal_label": portal_label,
        "lang": lang,
        "nav_items": nav_items,
        "upcoming_items": upcoming_items,
        "personalize_label": t("nav.personalize", lang),
        "personalize_active": active_path == "/personalize",
        "current_user": {
            "full_name": user.full_name,
            "email": user.email,
            "company_name": user.company.company_name if user.company else "Platform Administration",
            "avatar_url": f"/static/uploads/avatars/{user.avatar_filename}" if user.avatar_filename else "/static/img/logo-512.png",
            "totp_enabled": user.totp_enabled,
        },
        "notifications": [],
        "unread_notifications": 0,
        "is_admin_preview": is_admin_preview,
    }

    # Every real page an admin can see also gets quick links to every
    # portal — the "view all portals without logging in again" ask.
    if user.role == UserRole.ADMIN:
        context["admin_preview_links"] = [
            {**item, "label": t(item["key"], lang), "active": item["url"] == active_path}
            for item in _ADMIN_PREVIEW_LINKS
        ]

    return context
