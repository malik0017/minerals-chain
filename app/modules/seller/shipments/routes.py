"""
app/modules/seller/shipments/routes.py
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.permissions import require_seller_company
from app.database.base import get_db
from app.models.user import User, UserRole
from app.modules.shared import shipment_views as v

router = APIRouter(prefix="/seller/shipments", tags=["seller-shipments"])
BASE = "/seller/shipments"


@router.get("", name="seller_shipments")
def index(request: Request, db: Session = Depends(get_db), user: User = Depends(require_seller_company),
          status: str = "", q: str = "", page: int = 1):
    return v.page(request, db, user, UserRole.SELLER, BASE, status, q, page)


@router.get("/export.csv", name="seller_shipments_csv")
def export(db: Session = Depends(get_db), user: User = Depends(require_seller_company), status: str = "", q: str = ""):
    return v.export_csv(db, user, UserRole.SELLER, status, q)
