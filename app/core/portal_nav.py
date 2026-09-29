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
        {"icon": "bi-truck", "key": "nav.shipments", "url": "/seller/shipments"},
        {"icon": "bi-boxes", "key": "nav.inventory", "url": "/seller/inventory"},
        {"icon": "bi-box-arrow-up-right", "key": "nav.erp_export", "url": "/seller/erp-export"},
        {"icon": "bi-flag", "key": "nav.disputes", "url": "/seller/disputes"},
        {"icon": "bi-folder2-open", "key": "nav.documents", "url": "/account/documents"},
        {"icon": "bi-stars", "key": "nav.subscription", "url": "/account/subscription"},
    ],
    UserRole.BUYER: [
        {"icon": "bi-columns-gap", "key": "nav.dashboard", "url": "/buyer/dashboard"},
        {"icon": "bi-search", "key": "nav.browse_minerals", "url": "/buyer/browse"},
        {"icon": "bi-file-earmark-text", "key": "nav.my_rfqs", "url": "/buyer/rfqs"},
        {"icon": "bi-box-seam", "key": "nav.orders", "url": "/buyer/orders"},
        {"icon": "bi-truck", "key": "nav.shipments", "url": "/buyer/shipments"},
        {"icon": "bi-flag", "key": "nav.disputes", "url": "/buyer/disputes"},
        {"icon": "bi-folder2-open", "key": "nav.documents", "url": "/account/documents"},
        {"icon": "bi-stars", "key": "nav.subscription", "url": "/account/subscription"},
    ],
    UserRole.LAB: [
        {"icon": "bi-columns-gap", "key": "nav.dashboard", "url": "/lab/dashboard"},
        {"icon": "bi-eyedropper", "key": "nav.verification_requests", "url": "/lab/verification-requests"},
        {"icon": "bi-patch-check", "key": "nav.certificates", "url": "/lab/certificates"},
        {"icon": "bi-folder2-open", "key": "nav.documents", "url": "/account/documents"},
    ],
    UserRole.ADMIN: [
        {"heading": "nav.h_overview"},
        {"icon": "bi-speedometer", "key": "nav.control_center", "url": "/admin/control-center", "area": "dashboard"},
        {"icon": "bi-graph-up-arrow", "key": "nav.reports", "url": "/admin/reports", "area": "reports"},
        {"icon": "bi-bar-chart-line", "key": "nav.insights", "url": "/admin/reports/insights", "area": "reports"},
        {"heading": "nav.h_onboarding"},
        {"icon": "bi-inbox", "key": "nav.pending_approvals", "url": "/admin/approvals", "area": "approvals"},
        {"icon": "bi-shield-lock", "key": "nav.credential_checks", "url": "/admin/credential-checks", "area": "approvals"},
        {"icon": "bi-building", "key": "nav.all_companies", "url": "/admin/companies", "area": "companies"},
        {"icon": "bi-people", "key": "nav.users", "url": "/admin/users", "area": "users_view"},
        {"icon": "bi-folder2-open", "key": "nav.documents", "url": "/admin/documents", "area": "companies"},
        {"icon": "bi-eyedropper", "key": "nav.lab_partners", "url": "/admin/labs", "area": "labs"},
        {"heading": "nav.h_marketplace"},
        {"icon": "bi-diagram-3", "key": "nav.products", "url": "/admin/products", "area": "products"},
        {"icon": "bi-file-earmark-text", "key": "nav.rfqs", "url": "/admin/rfqs", "area": "rfqs"},
        {"icon": "bi-box-seam", "key": "nav.orders", "url": "/admin/orders", "area": "orders"},
        {"icon": "bi-truck", "key": "nav.shipments", "url": "/admin/shipments", "area": "orders"},
        {"icon": "bi-boxes", "key": "nav.inventory", "url": "/admin/inventory", "area": "orders"},
        {"icon": "bi-flag", "key": "nav.disputes", "url": "/admin/disputes", "area": "disputes"},
        {"icon": "bi-shield-check", "key": "nav.mineral_passports", "url": "/admin/passports", "area": "passports"},
        {"heading": "nav.h_finance"},
        {"icon": "bi-cash-coin", "key": "nav.finance", "url": "/admin/finance", "area": "finance"},
        {"icon": "bi-stars", "key": "nav.subscriptions", "url": "/admin/subscriptions", "area": "subscriptions"},
        {"icon": "bi-box-arrow-up-right", "key": "nav.erp_export", "url": "/admin/erp-export", "area": "finance"},
        {"heading": "nav.h_compliance"},
        {"icon": "bi-journal-text", "key": "nav.audit_log", "url": "/admin/audit-log", "area": "audit"},
        {"icon": "bi-person-lock", "key": "nav.data_requests", "url": "/admin/data-requests", "area": "data_requests"},
        {"heading": "nav.h_configuration"},
        {"icon": "bi-database-gear", "key": "nav.master_data", "url": "/admin/master-data", "area": "master_data"},
        {"icon": "bi-sliders", "key": "nav.system_settings", "url": "/admin/system-settings", "area": "system"},
        {"icon": "bi-hdd-stack", "key": "nav.backups", "url": "/admin/backups", "area": "system"},
        {"icon": "bi-activity", "key": "nav.monitoring", "url": "/admin/monitoring", "area": "system"},
        {"icon": "bi-key", "key": "nav.api_tokens", "url": "/admin/api-tokens", "area": "system"},
        {"icon": "bi-gear", "key": "nav.settings", "url": "/admin/settings", "area": "settings"},
    ],
}

_UPCOMING_ITEMS = {UserRole.SELLER: [], UserRole.BUYER: [], UserRole.LAB: [], UserRole.ADMIN: []}

_PORTAL_LABEL_KEY = {
    UserRole.SELLER: "portal.seller",
    UserRole.BUYER: "portal.buyer",
    UserRole.LAB: "portal.lab",
    UserRole.ADMIN: "portal.admin",
}

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

    from app.core.permissions import admin_can
    nav_items, pending_heading = [], None
    for item in _NAV_ITEMS[portal_role]:
        if "heading" in item:
            pending_heading = {"heading": True, "label": t(item["heading"], lang)}
            continue
        if item.get("area") and not admin_can(user, item["area"]):
            continue
        if pending_heading:
            nav_items.append(pending_heading)
            pending_heading = None
        active = item["url"] == active_path or (active_path or "").startswith(item["url"] + "/")
        nav_items.append({**item, "label": t(item["key"], lang), "active": active})
    if any(i.get("url") == active_path for i in nav_items):
        for i in nav_items:
            if "url" in i:
                i["active"] = i["url"] == active_path
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
