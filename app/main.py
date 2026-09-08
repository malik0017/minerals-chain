from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.auth import get_current_user_optional
from app.core.exceptions import CompanyNotApprovedException, ForbiddenException, NotAuthenticatedException
from app.database.base import get_db  # noqa: F401  (kept — several routes below import it directly too)
from app.models.user import User
from app.modules.admin.approvals.routes import router as admin_approvals_router
from app.modules.auth.routes import router as auth_router
from app.modules.buyer.dashboard.routes import router as buyer_dashboard_router
from app.modules.lab.dashboard.routes import router as lab_dashboard_router
from app.modules.seller.dashboard.routes import router as seller_dashboard_router
from app.modules.shared.routes import router as shared_router

app = FastAPI(title="Minerals Chain")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/assets", StaticFiles(directory="app/static"), name="assets_compat")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_router)
app.include_router(admin_approvals_router)
app.include_router(shared_router)
app.include_router(seller_dashboard_router)
app.include_router(buyer_dashboard_router)
app.include_router(lab_dashboard_router)


@app.exception_handler(NotAuthenticatedException)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url=request.url_for("login_form"), status_code=303)


@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException):
    return templates.TemplateResponse(request, "errors/403.html", {}, status_code=403)


@app.exception_handler(CompanyNotApprovedException)
async def company_not_approved_handler(request: Request, exc: CompanyNotApprovedException):
    # Batch 4: someone whose role matches a portal route but whose company
    # isn't APPROVED yet — send them to /home, which already knows how to
    # render the pending/rejected/suspended status page.
    return RedirectResponse(url=request.url_for("home"), status_code=303)


@app.get("/", name="root")
def root(request: Request, user: User | None = Depends(get_current_user_optional)):
    # Previously always redirected to /dashboard-test regardless of
    # login state, which is why visiting "/" never showed a login
    # screen. Now: logged in -> /home (which already knows how to route
    # to the right portal or status page); logged out -> /login.
    if user is not None:
        return RedirectResponse(url=request.url_for("home"))
    return RedirectResponse(url=request.url_for("login_form"))


@app.get("/dashboard-test", name="dashboard_home")
def dashboard_test(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
):
    """
    Renders app/templates/dashboard.html — kept as a visual/design
    reference page now that Batch 4 gives seller/buyer/lab their own
    real dashboards (base_portal.html). Nothing routes here for a
    logged-in user anymore (see modules/auth/routes.py's home()), but
    the page is left working and session-aware in case it's still
    useful as a design sandbox.
    """
    if user is not None:
        context = {
            "portal_label": f"{user.role.value.capitalize()} Portal"
            + (" (test)" if user.role.value != "admin" else ""),
            "lang": user.preferred_language,
            "current_user": {
                "full_name": user.full_name,
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
                "company_name": "Demo Mining Co.",
                "avatar_url": "/static/img/logo-512.png",  # placeholder until real avatars exist
            },
            "nav_items": [
                {"icon": "bi-speedometer2", "label": "Dashboard", "url": "/dashboard-test", "active": True},
            ],
            "notifications": [],
            "unread_notifications": 0,
        }

    return templates.TemplateResponse(request, "dashboard.html", context)


@app.get("/my-profile", name="my_profile")
def my_profile():
    return {"status": "stub — build in modules/shared or modules/auth"}


@app.get("/account-settings", name="account_settings")
def account_settings():
    return {"status": "stub"}


@app.get("/help", name="help_center")
def help_center():
    return {"status": "stub"}


@app.get("/terms", name="terms")
def terms():
    return {"status": "stub"}


@app.get("/privacy", name="privacy")
def privacy():
    return {"status": "stub"}
