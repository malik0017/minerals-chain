"""
app/modules/admin/erp_export/routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.permissions import require_admin
from app.database.base import get_db
from app.models.user import User, UserRole
from app.modules.shared import erp_export_views as v

router = APIRouter(prefix="/admin/erp-export", tags=["admin-erp-export"])
BASE = "/admin/erp-export"


@router.get("", name="admin_erp_export")
def index(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("finance")),
          msg: str | None = None, error: str | None = None):
    return v.page(request, db, admin, UserRole.ADMIN, BASE, None, msg, error)


@router.post("", name="admin_erp_export_build")
def build(db: Session = Depends(get_db), admin: User = Depends(require_admin("finance")),
          form: FormData = Depends(form_data)):
    return v.build(db, admin, BASE, None, form)


@router.get("/{run_id}/download", name="admin_erp_export_download")
def download(run_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin("finance"))):
    return v.download(db, admin, run_id, None)
