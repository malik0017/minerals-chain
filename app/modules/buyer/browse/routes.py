"""
app/modules/buyer/browse/routes.py
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import uuid

from app.core.permissions import require_active_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import product_repository

router = APIRouter(prefix="/buyer/browse", tags=["buyer-browse"])
from app.core.templates import templates


@router.get("", name="buyer_browse_index")
def browse_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_portal(UserRole.BUYER)),
    q: str | None = None,
    region: str = "",
    product: str = "",
    page: int = 1,
):
    # Batch M3: filters, plan-priority ordering, passport badge, paging
    from app.models.md_locations import Region
    from app.modules.shared.catalog_routes import product_choices
    rid = _uuid(region)
    pid = _uuid(product)
    products = product_repository.list_verified(db, search=q, region_id=rid, product_master_id=pid)
    total = len(products)
    pages = max(1, (total + 24) // 25)
    page = min(max(page, 1), pages)
    rows = products[(page - 1) * 25: page * 25]
    context = build_portal_context(user, UserRole.BUYER, active_path=request.url.path)
    from app.core.listing import qs
    context.update({"products": rows, "q": q or "", "region": region, "product": product, "total": total,
                    "page": page, "pages": pages, "qs": qs(q=q or "", region=region, product=product),
                    "regions": db.query(Region).filter(Region.is_active.is_(True)).order_by(Region.name_en).all(),
                    "catalog": product_choices(db), "badges": _badges(db, [p.id for p in rows])})
    return templates.TemplateResponse(request, "buyer/browse_index.html", context)


@router.get("/{product_id}", name="buyer_browse_detail")
def browse_detail(
    request: Request,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_active_portal(UserRole.BUYER)),
):
    product = product_repository.get_verified_by_id(db, product_id)
    if product is None:
        return RedirectResponse(url=request.url_for("buyer_browse_index"), status_code=303)

    context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/browse")
    context["product"] = product
    # Batch M3: declared spec + the valid COA (with results) and passport
    from app.models.certification import CertificationType
    from app.repositories import certification_repository
    from app.services import spec_service
    certs = certification_repository.list_for_product(db, product.id)
    context["spec_rows"] = spec_service.product_rows(db, product)
    context["coa"] = next((c for c in certs if c.cert_type == CertificationType.LAB_CERTIFICATE and c.is_currently_valid), None)
    context["passport"] = next((c for c in certs if c.cert_type == CertificationType.MINERAL_PASSPORT and c.is_currently_valid), None)
    return templates.TemplateResponse(request, "buyer/browse_detail.html", context)


def _uuid(v: str):
    try:
        return uuid.UUID(v) if v else None
    except ValueError:
        return None


def _badges(db: Session, product_ids: list) -> dict:
    """product_id -> {"passport": category|None, "coa": bool} for the list view."""
    from app.models.certification import Certification, CertificationScope, CertificationType
    out = {pid: {"passport": None, "coa": False} for pid in product_ids}
    if not product_ids:
        return out
    rows = (db.query(CertificationScope.product_id, Certification)
            .join(Certification, Certification.id == CertificationScope.certification_id)
            .filter(CertificationScope.product_id.in_(product_ids)).all())
    for pid, c in rows:
        if not c.is_currently_valid:
            continue
        if c.cert_type == CertificationType.MINERAL_PASSPORT:
            out[pid]["passport"] = c.category
        else:
            out[pid]["coa"] = True
    return out
