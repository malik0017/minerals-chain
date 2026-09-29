"""
app/modules/seller/erp_export/routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.permissions import require_seller_company
from app.database.base import get_db
from app.models.user import User, UserRole
from app.modules.shared import erp_export_views as v

router = APIRouter(prefix="/seller/erp-export", tags=["seller-erp-export"])
BASE = "/seller/erp-export"


@router.get("", name="seller_erp_export")
def index(request: Request, db: Session = Depends(get_db), user: User = Depends(require_seller_company),
          msg: str | None = None, error: str | None = None):
    return v.page(request, db, user, UserRole.SELLER, BASE, user.company, msg, error)


@router.post("", name="seller_erp_export_build")
def build(db: Session = Depends(get_db), user: User = Depends(require_seller_company),
          form: FormData = Depends(form_data)):
    return v.build(db, user, BASE, user.company, form)


@router.get("/{run_id}/download", name="seller_erp_export_download")
def download(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_seller_company)):
    return v.download(db, user, run_id, user.company)
