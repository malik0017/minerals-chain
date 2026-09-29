"""
app/modules/admin/subscriptions/routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.audit_log import AuditLog
from app.models.company import ApprovalStatus, Company, CompanyRole, SubscriptionTier
from app.models.subscription import Subscription, SubscriptionCharge, SubscriptionStatus
from app.models.user import User, UserRole
from app.services import subscription_service as subs

router = APIRouter(prefix="/admin/subscriptions", tags=["admin-subscriptions"])


@router.get("", name="admin_subscriptions")
def index(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("subscriptions")),
          tier: str = "", q: str = "", page: int = 1, tab: str = "companies", msg: str | None = None, error: str | None = None):
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/subscriptions")
    if tab == "charges":
        cq = db.query(SubscriptionCharge).order_by(SubscriptionCharge.created_at.desc())
        rows, total, page, pages = paginate(cq, page)
        context.update({"charges": rows})
    else:
        cq = db.query(Company).filter(Company.role != CompanyRole.LAB, Company.status == ApprovalStatus.APPROVED)
        if tier in [t.value for t in SubscriptionTier]:
            cq = cq.filter(Company.subscription_tier == SubscriptionTier(tier))
        if q.strip():
            cq = cq.filter(Company.company_name.ilike(f"%{q.strip()}%"))
        rows, total, page, pages = paginate(cq.order_by(Company.company_name), page)
        context.update({"companies": [(c, subs.status_info(db, c)) for c in rows]})
    counts = {t.value: db.query(Company).filter(Company.subscription_tier == t).count() for t in SubscriptionTier}
    context.update({"tab": tab, "tier": tier, "q": q, "tiers": list(SubscriptionTier), "counts": counts,
                    "page": page, "pages": pages, "total": total, "qs": qs(tab=tab, tier=tier, q=q),
                    "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin/subscriptions.html", context)


@router.post("/run-lifecycle", name="admin_subscriptions_run")
def run(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("subscriptions"))):
    stats = subs.run_lifecycle(db)
    msg = f"Lifecycle run: {stats['notified']} expiry notices, {stats['grace']} moved to grace, {stats['expired']} expired → entry."
    return RedirectResponse(url=f"{request.url_for('admin_subscriptions')}?msg={quote(msg)}", status_code=303)


@router.post("/{company_id}/change", name="admin_subscription_change")
def change(request: Request, company_id: uuid.UUID, db: Session = Depends(get_db),
           admin: User = Depends(require_admin("subscriptions")), tier: str = Form(...), action: str = Form("change")):
    company = db.get(Company, company_id)
    back = str(request.url_for("admin_subscriptions"))
    if company is None:
        return RedirectResponse(url=back, status_code=303)
    try:
        if action == "renew":
            subs.renew(db, company, admin)
        else:
            subs.change_plan(db, company, tier, admin, by_admin=True)
    except subs.SubscriptionError as exc:
        db.rollback()
        return RedirectResponse(url=f"{back}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"{back}?msg={quote(company.company_name + ' updated.')}", status_code=303)


@router.post("/charges/{charge_id}", name="admin_subscription_charge")
def charge_status(request: Request, charge_id: uuid.UUID, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin("finance")), status: str = Form(...), reference: str = Form("")):
    from datetime import datetime, timezone
    ch = db.get(SubscriptionCharge, charge_id)
    back = f"{request.url_for('admin_subscriptions')}?tab=charges"
    if ch is None or status not in ("pending", "paid", "waived", "cancelled"):
        return RedirectResponse(url=back, status_code=303)
    old = ch.status
    ch.status = status
    ch.payment_reference = reference.strip() or ch.payment_reference
    ch.paid_at = datetime.now(timezone.utc) if status == "paid" else ch.paid_at
    db.add(AuditLog(actor_user_id=admin.id, action="subscription_charge_updated", target_type="subscription_charge",
                    target_id=ch.id, details=f"{ch.reference}: {old} → {status}"))
    db.commit()
    return RedirectResponse(url=back + "&msg=Saved", status_code=303)
