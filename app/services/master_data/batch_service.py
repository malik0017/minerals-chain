"""
app/services/master_data/batch_service.py

Batch I — ERP Master Data PDF §10:
    Specification → Lab Result → Automatic Validation → PASS / FAIL
    → Batch Release / Quarantine

Spec lookup order for a batch's product: product-level override
(QualitySpecification.product_master_id) first, then the product's grade
default (QualitySpecification.grade_id). Only active spec rows count.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.system_settings import get_setting
from app.models.batch import Batch, BatchQualityResult, BatchStatus, QCStatus
from app.models.md_product import ProductMaster
from app.models.md_quality import QualitySpecification


def applicable_specs(db: Session, product_master_id) -> dict:
    """parameter_id -> QualitySpecification (product override wins over grade)."""
    pm = db.get(ProductMaster, product_master_id)
    if pm is None:
        return {}
    specs = {}
    if pm.grade_id:
        for s in db.execute(select(QualitySpecification).where(
                QualitySpecification.grade_id == pm.grade_id, QualitySpecification.is_active.is_(True))).scalars():
            specs[s.parameter_id] = s
    for s in db.execute(select(QualitySpecification).where(
            QualitySpecification.product_master_id == pm.id, QualitySpecification.is_active.is_(True))).scalars():
        specs[s.parameter_id] = s
    return specs


def judge(value, spec_min, spec_max) -> bool:
    if spec_min is not None and value < spec_min:
        return False
    if spec_max is not None and value > spec_max:
        return False
    return True


def judge_result(db: Session, result: BatchQualityResult) -> None:
    """Snapshot the applicable spec onto the result row and set passed."""
    batch = db.get(Batch, result.batch_id)
    spec = applicable_specs(db, batch.product_master_id).get(result.parameter_id) if batch else None
    if spec is None:
        result.spec_min = result.spec_max = None
        result.uom_code = None
        result.passed = None  # nothing to judge against — informational value
        return
    result.spec_min, result.spec_max = spec.min_value, spec.max_value
    result.uom_code = spec.uom.code if spec.uom else None
    if result.test_method_id is None:
        result.test_method_id = spec.test_method_id
    result.passed = judge(result.measured_value, spec.min_value, spec.max_value)


def evaluate_batch(db: Session, batch: Batch, actor=None) -> Batch:
    """Recompute qc_status from the results, then auto-release/reject if enabled.
    Flushes; the caller commits."""
    specs = applicable_specs(db, batch.product_master_id)
    results = {r.parameter_id: r for r in batch.results}
    for r in results.values():
        judge_result(db, r)
    any_failed = any(r.passed is False for r in results.values())
    mandatory_missing = [p for p, s in specs.items() if s.is_mandatory and p not in results]
    if any_failed:
        batch.qc_status = QCStatus.FAILED
    elif specs and not mandatory_missing and results:
        batch.qc_status = QCStatus.PASSED
    else:
        batch.qc_status = QCStatus.PENDING
    batch.qc_evaluated_at = datetime.now(timezone.utc)

    if get_setting(db, "qc_auto_release") and batch.status == BatchStatus.QUARANTINE:
        if batch.qc_status == QCStatus.PASSED:
            batch.status = BatchStatus.RELEASED
            batch.released_at = datetime.now(timezone.utc)
            batch.released_by_user_id = actor.id if actor else None
        elif batch.qc_status == QCStatus.FAILED:
            batch.status = BatchStatus.REJECTED
    db.flush()
    return batch


def set_status(db: Session, batch: Batch, new_status: BatchStatus, actor) -> Batch:
    """Manual release / quarantine / block from the QC page. A batch that
    FAILED QC can never be released by hand — that's the whole point of QC."""
    if new_status == BatchStatus.RELEASED and batch.qc_status != QCStatus.PASSED:
        raise ValueError("Only a batch whose QC status is PASSED can be released.")
    batch.status = new_status
    if new_status == BatchStatus.RELEASED:
        batch.released_at = datetime.now(timezone.utc)
        batch.released_by_user_id = actor.id
    db.flush()
    return batch


def missing_parameters(db: Session, batch: Batch) -> list[QualitySpecification]:
    specs = applicable_specs(db, batch.product_master_id)
    have = {r.parameter_id for r in batch.results}
    return [s for p, s in specs.items() if p not in have]
