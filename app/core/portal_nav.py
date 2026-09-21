"""
app/core/portal_nav.py
"""
from app.core.localization import t
from app.models.user import User, UserRole

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
        {"icon": "bi-journal-text", "key": "nav.audit_log", "url": "/admin/audit-log"},
        {"icon": "bi-gear", "key": "nav.settings", "url": "/admin/settings"},
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
   
    is_admin_preview = user.role == UserRole.ADMIN and portal_role != UserRole.ADMIN
    lang = user.preferred_language

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


    if user.role == UserRole.ADMIN:
        preview_links = _ADMIN_PREVIEW_LINKS if is_admin_preview else [
            item for item in _ADMIN_PREVIEW_LINKS if item["url"] != "/admin/approvals"
        ]
        context["admin_preview_links"] = [
            {**item, "label": t(item["key"], lang), "active": item["url"] == active_path}
            for item in preview_links
        ]

    return context
