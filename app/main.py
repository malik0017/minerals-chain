from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.auth import get_current_user_optional
from app.core.csrf_middleware import CSRFMiddleware
from app.core.config import settings
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.translation import TranslationMiddleware
from app.services.monitoring_service import MetricsMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
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

from app.core import production  # noqa: E402

production.configure_logging(settings.LOG_LEVEL)
production.enforce(settings)
_prod = settings.APP_ENV == "production"
app = FastAPI(title="Minerals Chain", docs_url=None if _prod else "/docs", redoc_url=None if _prod else "/redoc",
              openapi_url=None if _prod else "/openapi.json")

app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TranslationMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=[h.strip() for h in settings.FORWARDED_ALLOW_IPS.split(",") if h.strip()])

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
from app.modules.admin.backups.routes import router as admin_backups_router  # noqa: E402
app.include_router(admin_backups_router)
from app.modules.public.security_routes import router as security_router  # noqa: E402
app.include_router(security_router)
from app.modules.seller.inventory.routes import router as seller_inventory_router  # noqa: E402
app.include_router(seller_inventory_router)
from app.modules.admin.inventory.routes import router as admin_inventory_router  # noqa: E402
app.include_router(admin_inventory_router)
from app.modules.admin.erp_export.routes import router as admin_erp_export_router  # noqa: E402
app.include_router(admin_erp_export_router)
from app.modules.seller.erp_export.routes import router as seller_erp_export_router  # noqa: E402
app.include_router(seller_erp_export_router)
from app.modules.admin.shipments.routes import router as admin_shipments_router  # noqa: E402
app.include_router(admin_shipments_router)
from app.modules.seller.shipments.routes import router as seller_shipments_router  # noqa: E402
app.include_router(seller_shipments_router)
from app.modules.buyer.shipments.routes import router as buyer_shipments_router  # noqa: E402
app.include_router(buyer_shipments_router)
from app.modules.shared.document_library_routes import router as document_library_router  # noqa: E402
app.include_router(document_library_router)
from app.modules.admin.documents.routes import router as admin_documents_router  # noqa: E402
app.include_router(admin_documents_router)
from app.modules.admin.monitoring.routes import router as admin_monitoring_router  # noqa: E402
app.include_router(admin_monitoring_router)
from app.modules.admin.credentials.routes import router as admin_credentials_router  # noqa: E402
app.include_router(admin_credentials_router)
from app.modules.api.v1 import router as api_v1_router  # noqa: E402
app.include_router(api_v1_router)
from app.modules.shared.api_token_routes import router as api_token_router  # noqa: E402
app.include_router(api_token_router)
from app.modules.public.pwa_routes import router as pwa_router  # noqa: E402
app.include_router(pwa_router)

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


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    from fastapi.exception_handlers import http_exception_handler
    if exc.status_code == 404 and not request.url.path.startswith("/api/") and "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(request, "errors/404.html", {"lang": request.cookies.get("mc_lang", "en")}, status_code=404)
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception):
    from fastapi.responses import HTMLResponse, JSONResponse
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Internal server error."}, status_code=500)
    return HTMLResponse(templates.get_template("errors/500.html").render(), status_code=500)


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


@app.get("/healthz", include_in_schema=False)
def healthz():
    from sqlalchemy import text
    from app.database.base import SessionLocal
    from fastapi.responses import JSONResponse
    db = SessionLocal()
    try:
        rev = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return {"status": "ok", "db": "ok", "revision": rev}
    except Exception as exc:
        return JSONResponse({"status": "error", "db": type(exc).__name__}, status_code=503)
    finally:
        db.close()


@app.get("/", name="root")
def root(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user is not None:
        return RedirectResponse(url=request.url_for("home"))
    return RedirectResponse(url=request.url_for("login_form"))


def _content_page(request: Request, slug: str, db, user):
    from app.core.localization import DEFAULT_LANGUAGE
    from app.models.content_page import ContentPage
    lang = user.preferred_language if user else request.cookies.get("mc_lang", DEFAULT_LANGUAGE)
    page = db.query(ContentPage).filter(ContentPage.slug == slug, ContentPage.is_published.is_(True)).first()
    if page is None:
        return templates.TemplateResponse(request, "errors/404.html", {"lang": lang}, status_code=404)
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
