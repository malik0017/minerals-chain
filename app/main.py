from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.auth import get_current_user_optional
from app.core.csrf_middleware import CSRFMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.translation import TranslationMiddleware
from app.core.exceptions import (
    AdminRedirectException,
    CompanyNotApprovedException,
    ForbiddenException,
    NotAuthenticatedException,
    RateLimitExceededException,
)
from app.core.templates import templates
from app.database.base import get_db  
from app.models.user import User
from app.modules.admin.approvals.routes import router as admin_approvals_router
from app.modules.admin.audit_log.routes import router as admin_audit_log_router
from app.modules.admin.batches.routes import router as admin_batches_router
from app.modules.admin.control_center.routes import router as admin_control_center_router
from app.modules.admin.master_data.routes import router as admin_master_data_router
from app.modules.admin.orders.routes import router as admin_orders_router
from app.modules.admin.companies.routes import router as admin_companies_router
from app.modules.admin.passports.routes import router as admin_passports_router
from app.modules.admin.settings.routes import router as admin_settings_router
from app.modules.admin.users.routes import router as admin_users_router
from app.modules.auth.routes import router as auth_router
from app.modules.buyer.browse.routes import router as buyer_browse_router
from app.modules.buyer.dashboard.routes import router as buyer_dashboard_router
from app.modules.buyer.rfq.routes import router as buyer_rfq_router
from app.modules.buyer.orders.routes import router as buyer_orders_router
from app.modules.lab.dashboard.routes import router as lab_dashboard_router
from app.modules.lab.verification.routes import router as lab_verification_router
from app.modules.public.routes import router as public_router
from app.modules.seller.dashboard.routes import router as seller_dashboard_router
from app.modules.seller.listings.routes import router as seller_listings_router
from app.modules.seller.rfq_inbox.routes import router as seller_rfq_inbox_router
from app.modules.seller.quotations.routes import router as seller_quotations_router
from app.modules.seller.orders.routes import router as seller_orders_router
from app.modules.shared.personalize.routes import router as personalize_router
from app.modules.shared.profile.routes import router as profile_router
from app.modules.shared.routes import router as shared_router
from app.modules.shared.privacy_routes import router as privacy_router
from app.modules.shared.subscription_routes import router as subscription_router
from app.modules.admin.subscriptions.routes import router as admin_subscriptions_router
from app.modules.shared.dispute_routes import buyer_router as buyer_disputes_router, seller_router as seller_disputes_router
from app.modules.admin.disputes.routes import router as admin_disputes_router
from app.modules.shared.certificate_routes import router as certificate_router
from app.modules.admin.labs.routes import router as admin_labs_router
from app.modules.shared.catalog_routes import router as catalog_router
from app.modules.admin.marketplace.routes import router as admin_marketplace_router
from app.modules.admin.reports.routes import router as admin_reports_router
from app.modules.shared.order_document_routes import (admin_router as admin_order_docs_router,
    buyer_router as buyer_order_docs_router, seller_router as seller_order_docs_router)
from app.modules.admin.data_requests.routes import router as admin_data_requests_router

app = FastAPI(title="Minerals Chain")

app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TranslationMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/assets", StaticFiles(directory="app/static"), name="assets_compat")

app.include_router(auth_router)
app.include_router(admin_approvals_router)
app.include_router(admin_audit_log_router)
app.include_router(admin_companies_router)
app.include_router(admin_passports_router)
app.include_router(admin_settings_router)
app.include_router(admin_users_router)
app.include_router(admin_master_data_router)
app.include_router(admin_batches_router)
app.include_router(admin_control_center_router)
app.include_router(admin_orders_router)
app.include_router(privacy_router)
app.include_router(admin_data_requests_router)
app.include_router(subscription_router)
app.include_router(admin_subscriptions_router)
app.include_router(buyer_disputes_router)
app.include_router(seller_disputes_router)
app.include_router(admin_disputes_router)
app.include_router(certificate_router)
app.include_router(admin_labs_router)
app.include_router(catalog_router)
app.include_router(admin_marketplace_router)
app.include_router(admin_reports_router)
app.include_router(buyer_order_docs_router)
app.include_router(seller_order_docs_router)
app.include_router(admin_order_docs_router)
app.include_router(shared_router)
app.include_router(personalize_router)
app.include_router(profile_router)
app.include_router(public_router)
app.include_router(seller_dashboard_router)
app.include_router(seller_listings_router)
app.include_router(seller_rfq_inbox_router)
app.include_router(seller_quotations_router)
app.include_router(seller_orders_router)
app.include_router(buyer_dashboard_router)
app.include_router(buyer_browse_router)
app.include_router(buyer_rfq_router)
app.include_router(buyer_orders_router)
app.include_router(lab_dashboard_router)
app.include_router(lab_verification_router)

@app.exception_handler(NotAuthenticatedException)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url=request.url_for("login_form"), status_code=303)


@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException):
    return templates.TemplateResponse(request, "errors/403.html", {}, status_code=403)


@app.exception_handler(CompanyNotApprovedException)
async def company_not_approved_handler(request: Request, exc: CompanyNotApprovedException):
    return RedirectResponse(url=request.url_for("home"), status_code=303)


@app.exception_handler(AdminRedirectException)
async def admin_redirect_handler(request: Request, exc: AdminRedirectException):
    url = str(request.url_for(exc.redirect_route_name))
    if exc.query:
        url = f"{url}?{exc.query}"
    return RedirectResponse(url=url, status_code=303)


@app.exception_handler(RateLimitExceededException)
async def rate_limit_handler(request: Request, exc: RateLimitExceededException):
    retry_after_minutes = max(1, exc.retry_after_seconds // 60)
    response = templates.TemplateResponse(
        request,
        "errors/rate_limited.html",
        {"lang": "en", "retry_after_minutes": retry_after_minutes},
        status_code=429,
    )
    response.headers["Retry-After"] = str(exc.retry_after_seconds)
    return response


@app.get("/", name="root")
def root(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user is not None:
        return RedirectResponse(url=request.url_for("home"))
    return RedirectResponse(url=request.url_for("login_form"))


@app.get("/dashboard-test", name="dashboard_home")
def dashboard_test(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
):

    if user is not None:
        context = {
            "portal_label": f"{user.role.value.capitalize()} Portal"
            + (" (test)" if user.role.value != "admin" else ""),
            "lang": user.preferred_language,
            "current_user": {
                "full_name": user.full_name,
                "email": user.email,
                "company_name": user.company.company_name if user.company else "Platform Administration",
                "avatar_url": "/static/img/logo-512.png",
            },
            "nav_items": [
                {"icon": "bi-speedometer2", "label": "Dashboard", "url": "/dashboard-test", "active": True},
            ],
            "notifications": [],
            "unread_notifications": 0,
        }
    else:
        context = {
            "portal_label": "Seller Portal (test)",
            "lang": "en",
            "current_user": {
                "full_name": "Test User",
                "email": "test@example.com",
                "company_name": "Demo Mining Co.",
                "avatar_url": "/static/img/logo-512.png", 
            },
            "nav_items": [
                {"icon": "bi-speedometer2", "label": "Dashboard", "url": "/dashboard-test", "active": True},
            ],
            "notifications": [],
            "unread_notifications": 0,
        }

    return templates.TemplateResponse(request, "dashboard.html", context)


def _content_page(request: Request, slug: str, db, user):
    from app.core.localization import DEFAULT_LANGUAGE
    from app.models.content_page import ContentPage
    lang = user.preferred_language if user else request.cookies.get("mc_lang", DEFAULT_LANGUAGE)
    page = db.query(ContentPage).filter(ContentPage.slug == slug, ContentPage.is_published.is_(True)).first()
    if page is None:
        return templates.TemplateResponse(request, "errors/403.html", {"lang": lang}, status_code=404)
    use_ar = lang == "ar" and page.body_ar
    return templates.TemplateResponse(request, "public/content_page.html", {
        "lang": lang, "page": page,
        "title": (page.title_ar or page.title_en) if lang == "ar" else page.title_en,
        "body": page.body_ar if use_ar else page.body_en,
    })


@app.get("/help", name="help_center")
def help_center(request: Request, db=Depends(get_db), user: User | None = Depends(get_current_user_optional)):
    return _content_page(request, "help", db, user)


@app.get("/terms", name="terms")
def terms(request: Request, db=Depends(get_db), user: User | None = Depends(get_current_user_optional)):
    return _content_page(request, "terms", db, user)


@app.get("/privacy", name="privacy")
def privacy(request: Request, db=Depends(get_db), user: User | None = Depends(get_current_user_optional)):
    return _content_page(request, "privacy", db, user)


@app.get("/pages/{slug}", name="content_page")
def content_page(slug: str, request: Request, db=Depends(get_db), user: User | None = Depends(get_current_user_optional)):
    return _content_page(request, slug, db, user)
