"""
app/modules/admin/batches/routes.py
"""
import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.permissions import require_admin, require_portal
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.audit_log import AuditLog
from app.models.batch import Batch, BatchQualityResult, BatchStatus
from app.models.md_quality import QualityParameter
from app.models.user import User, UserRole
from app.repositories import audit_log_repository
from app.services.master_data import batch_service

router = APIRouter(prefix="/admin/batches", tags=["admin-batches"])


def _back(request: Request, batch_id, msg=None, error=None):
    url = str(request.url_for("admin_batch_qc", batch_id=batch_id))
    q = "&".join(x for x in (f"msg={quote(msg)}" if msg else "", f"error={quote(error)}" if error else "") if x)
    return RedirectResponse(url=url + (f"?{q}" if q else ""), status_code=303)


@router.get("/{batch_id}/qc", name="admin_batch_qc")
def qc_page(request: Request, batch_id: uuid.UUID, db: Session = Depends(get_db),
            admin: User = Depends(require_admin("master_data")),
            msg: str | None = None, error: str | None = None):
    batch = db.get(Batch, batch_id)
    if batch is None:
        return RedirectResponse(url=request.url_for("admin_master_data_list", entity_key="batches"), status_code=303)
    specs = batch_service.applicable_specs(db, batch.product_master_id)
    results = {r.parameter_id: r for r in batch.results}
    rows = []
    for pid, spec in specs.items():
        rows.append({"param": spec.parameter, "spec": spec, "result": results.get(pid)})
    extra = [r for pid, r in results.items() if pid not in specs]
    lineage = []
    node = batch.parent_batch
    while node is not None and len(lineage) < 10:
        lineage.append(node)
        node = node.parent_batch
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/master-data")
    context.update({
        "batch": batch, "rows": rows, "extra_results": extra, "lineage": lineage,
        "parameters": db.query(QualityParameter).filter(QualityParameter.is_active.is_(True)).order_by(QualityParameter.sort_order, QualityParameter.code).all(),
        "statuses": [BatchStatus.QUARANTINE, BatchStatus.RELEASED, BatchStatus.BLOCKED],
        "msg": msg, "error": error,
    })
    return templates.TemplateResponse(request, "admin/batch_qc.html", context)


@router.post("/{batch_id}/results", name="admin_batch_add_result")
def add_result(request: Request, batch_id: uuid.UUID, db: Session = Depends(get_db),
               admin: User = Depends(require_admin("master_data")),
               parameter_id: uuid.UUID = Form(...), measured_value: str = Form(...)):
    batch = db.get(Batch, batch_id)
    if batch is None:
        return RedirectResponse(url=request.url_for("admin_master_data_index"), status_code=303)
    try:
        value = Decimal(measured_value.strip())
    except (InvalidOperation, AttributeError):
        return _back(request, batch_id, error=f"'{measured_value}' is not a number.")
    result = next((r for r in batch.results if r.parameter_id == parameter_id), None)
    if result is None:
        result = BatchQualityResult(batch_id=batch.id, parameter_id=parameter_id, measured_value=value)
        db.add(result)
        batch.results.append(result)
    else:
        result.measured_value = value
    db.flush()
    batch_service.judge_result(db, result)
    batch_service.evaluate_batch(db, batch, actor=admin)
    audit_log_repository.create(db, AuditLog(
        actor_user_id=admin.id, action="batch_result_recorded", target_type="batch", target_id=batch.id,
        details=f"{batch.batch_number}: {result.parameter.code if result.parameter else parameter_id} = {value} "
                f"({'PASS' if result.passed else 'FAIL' if result.passed is False else 'no spec'}); QC now {batch.qc_status.value}",
    ))
    db.commit()
    return _back(request, batch_id, msg=f"Result saved. QC status: {batch.qc_status.value.upper()}, batch {batch.status.value}.")


@router.post("/{batch_id}/evaluate", name="admin_batch_evaluate")
def evaluate(request: Request, batch_id: uuid.UUID, db: Session = Depends(get_db),
             admin: User = Depends(require_admin("master_data"))):
    batch = db.get(Batch, batch_id)
    if batch is None:
        return RedirectResponse(url=request.url_for("admin_master_data_index"), status_code=303)
    batch_service.evaluate_batch(db, batch, actor=admin)
    db.commit()
    return _back(request, batch_id, msg=f"Re-evaluated: QC {batch.qc_status.value.upper()}, batch {batch.status.value}.")


@router.post("/{batch_id}/status", name="admin_batch_set_status")
def set_status(request: Request, batch_id: uuid.UUID, db: Session = Depends(get_db),
               admin: User = Depends(require_admin("master_data")), status: str = Form(...)):
    batch = db.get(Batch, batch_id)
    if batch is None:
        return RedirectResponse(url=request.url_for("admin_master_data_index"), status_code=303)
    try:
        new_status = BatchStatus(status)
        old = batch.status.value
        batch_service.set_status(db, batch, new_status, admin)
    except ValueError as exc:
        db.rollback()
        return _back(request, batch_id, error=str(exc))
    audit_log_repository.create(db, AuditLog(
        actor_user_id=admin.id, action="batch_status_changed", target_type="batch", target_id=batch.id,
        details=f"{batch.batch_number}: {old} → {new_status.value}",
    ))
    db.commit()
    return _back(request, batch_id, msg=f"Batch is now {new_status.value}.")
