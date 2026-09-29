"""
app/modules/shared/catalog_routes.py
"""
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_required
from app.database.base import get_db
from app.models.md_commercial import Incoterm
from app.models.md_product import ProductMaster
from app.models.user import User
from app.services import spec_service

router = APIRouter(prefix="/catalog", tags=["catalog"])


def product_choices(db: Session) -> list[ProductMaster]:
    return db.query(ProductMaster).filter(ProductMaster.is_active.is_(True)).order_by(ProductMaster.name_en).all()


def incoterm_choices(db: Session) -> list[Incoterm]:
    return db.query(Incoterm).filter(Incoterm.is_active.is_(True)).order_by(Incoterm.sort_order, Incoterm.code).all()


@router.get("/specs", name="catalog_specs")
def catalog_specs(product_master_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user_required)):
    pm = db.get(ProductMaster, product_master_id)
    rows = spec_service.catalog_rows(db, product_master_id)
    return JSONResponse({
        "product": None if pm is None else {"name": pm.name_en, "code": pm.code},
        "rows": [{"parameter_id": str(r["parameter_id"]) if r["parameter_id"] else "", "parameter": r["parameter"],
                  "min": "" if r["min"] is None else f"{r['min'].normalize():f}",
                  "max": "" if r["max"] is None else f"{r['max'].normalize():f}",
                  "unit": r["unit"] or "", "test_method": r["test_method"] or ""} for r in rows]})
