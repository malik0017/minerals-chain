"""
app/services/master_data/service.py

Generic CRUD + CSV engine for every Entity in registry.py. Routes never
touch models directly — they call these functions, which:
  * convert/validate form or CSV strings by field type,
  * resolve FKs (UUID from the form, natural key such as `code` from CSV),
  * run per-entity hooks (auto codes, QC evaluation, cross-field rules),
  * write one AuditLog row per change (BRD §6.8: material admin actions
    are logged with timestamp and administrator identity),
  * turn database integrity errors into a readable MasterDataError
    ("in use — deactivate instead") instead of a 500.
"""
import csv
import io
import re
import uuid
from dataclasses import dataclass, field as dc_field
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories import audit_log_repository
from app.services.master_data import batch_service
from app.services.master_data.registry import BY_KEY, Entity, Field, get_entity


class MasterDataError(ValueError):
    pass


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = dc_field(default_factory=list)


# ---------------------------------------------------------------- labels / keys

def label_of(entity: Entity, obj) -> str:
    if obj is None:
        return ""
    if entity.label_attr:
        value = getattr(obj, entity.label_attr, None)
        if entity.key == "listings":
            return f"{value} — {str(obj.id)[:8]}"
        return str(value)
    return str(obj)


def natural_key_str(db: Session, entity: Entity, obj) -> str:
    parts = []
    for name in entity.natural_key:
        f = _field(entity, name)
        value = getattr(obj, name)
        if f is not None and f.type == "fk" and value is not None:
            target = BY_KEY[f.fk]
            ref = db.get(target.model, value)
            parts.append(natural_key_str(db, target, ref) if ref else "")
        else:
            parts.append("" if value is None else str(value))
    return "/".join(parts)


def resolve_natural_key(db: Session, entity: Entity, key: str):
    """Inverse of natural_key_str — used by CSV import for FK columns."""
    key = (key or "").strip()
    if not key:
        return None
    if entity.natural_key == ("id",):
        try:
            return db.get(entity.model, uuid.UUID(key))
        except ValueError:
            return None
    raw_parts = key.split("/") if len(entity.natural_key) > 1 else [key]
    if len(raw_parts) != len(entity.natural_key):
        return None
    query = select(entity.model)
    for name, part in zip(entity.natural_key, raw_parts):
        f = _field(entity, name)
        if f is not None and f.type == "fk":
            ref = resolve_natural_key(db, BY_KEY[f.fk], part)
            if part and ref is None:
                return None
            query = query.where(getattr(entity.model, name) == (ref.id if ref else None))
        else:
            query = query.where(getattr(entity.model, name) == part)
    return db.execute(query).scalars().first()


def _field(entity: Entity, name: str) -> Field | None:
    return next((f for f in entity.fields if f.name == name), None)


# ---------------------------------------------------------------- reads

def fk_choices(db: Session, fk_key: str, include_id=None) -> list[tuple[str, str]]:
    target = BY_KEY[fk_key]
    query = select(target.model)
    if target.has_active and hasattr(target.model, "is_active"):
        cond = target.model.is_active.is_(True)
        if include_id is not None:
            cond = or_(cond, target.model.id == include_id)
        query = query.where(cond)
    for col in target.order_by:
        query = query.order_by(getattr(target.model, col))
    rows = db.execute(query.limit(1000)).scalars().all()
    return [(str(r.id), label_of(target, r)) for r in rows]


def list_rows(db: Session, entity: Entity, q: str | None = None, active: str | None = None,
              page: int = 1, page_size: int = 25) -> tuple[list, int]:
    model = entity.model
    query = select(model)
    count_q = select(func.count()).select_from(model)
    conds = []
    if q and entity.search_fields:
        like = f"%{q.strip()}%"
        conds.append(or_(*[getattr(model, f).ilike(like) for f in entity.search_fields]))
    if entity.has_active and active in ("1", "0"):
        conds.append(model.is_active.is_(active == "1"))
    for c in conds:
        query = query.where(c)
        count_q = count_q.where(c)
    total = db.execute(count_q).scalar_one()
    for col in entity.order_by:
        query = query.order_by(getattr(model, col))
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return list(rows), total


def count_rows(db: Session, entity: Entity) -> int:
    return db.execute(select(func.count()).select_from(entity.model)).scalar_one()


def get_row(db: Session, entity: Entity, row_id: uuid.UUID):
    return db.get(entity.model, row_id)


def display_value(db: Session, entity: Entity, obj, name: str) -> str:
    """Human-readable cell value for list tables."""
    f = _field(entity, name)
    value = getattr(obj, name, None)
    if value is None:
        return ""
    if f is not None and f.type == "fk":
        target = BY_KEY[f.fk]
        ref = db.get(target.model, value)
        return label_of(target, ref) if ref else "?"
    if hasattr(value, "value"):  # enum
        return value.value
    if isinstance(value, Decimal):
        return f"{value.normalize():f}"
    return str(value)


def column_default(entity: Entity, name: str):
    col = entity.model.__table__.c.get(name)
    if col is not None and col.default is not None and getattr(col.default, "is_scalar", False):
        value = col.default.arg
        return value.value if hasattr(value, "value") else value
    return None


def form_values(entity: Entity, obj=None) -> dict[str, object]:
    out = {}
    for f in entity.fields:
        value = getattr(obj, f.name, None) if obj is not None else column_default(entity, f.name)
        if hasattr(value, "value"):
            value = value.value
        if isinstance(value, Decimal):
            value = f"{value.normalize():f}"
        if f.type == "bool":
            out[f.name] = bool(value)
        else:
            out[f.name] = "" if value is None else str(value)
    return out


# ---------------------------------------------------------------- parsing

def _convert(db: Session, f: Field, raw, from_csv: bool, entity: Entity | None = None):
    if f.type == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw or "").strip().lower() in ("1", "true", "yes", "on", "y")
    text = "" if raw is None else str(raw).strip()
    if text == "":
        if f.required:
            raise MasterDataError(f"{f.label} is required.")
        return None
    if f.type == "int":
        try:
            return int(text)
        except ValueError:
            raise MasterDataError(f"{f.label}: '{text}' is not a whole number.")
    if f.type == "decimal":
        try:
            return Decimal(text)
        except InvalidOperation:
            raise MasterDataError(f"{f.label}: '{text}' is not a number.")
    if f.type == "date":
        try:
            return date.fromisoformat(text)
        except ValueError:
            raise MasterDataError(f"{f.label}: '{text}' is not a date (YYYY-MM-DD).")
    if f.type == "choice":
        if text not in f.choices:
            raise MasterDataError(f"{f.label}: '{text}' must be one of {', '.join(f.choices)}.")
        return text
    if f.type == "fk":
        target = BY_KEY[f.fk]
        if from_csv:
            ref = resolve_natural_key(db, target, text)
        else:
            try:
                ref = db.get(target.model, uuid.UUID(text))
            except ValueError:
                ref = None
        if ref is None:
            raise MasterDataError(f"{f.label}: '{text}' not found in {target.title}.")
        return ref.id
    if f.name == "code":
        # Subscription plan codes ARE the SubscriptionTier enum values (lowercase).
        return text.lower() if entity is not None and entity.key == "subscription-plans" else text.upper()
    return text


def parse_values(db: Session, entity: Entity, raw: dict, from_csv: bool = False,
                 only_present: bool = False) -> tuple[dict, list[str]]:
    values, errors = {}, []
    for f in entity.fields:
        if f.readonly:
            continue
        if only_present and f.name not in raw:
            continue
        try:
            values[f.name] = _convert(db, f, raw.get(f.name), from_csv, entity)
        except MasterDataError as exc:
            errors.append(str(exc))
    return values, errors


# ---------------------------------------------------------------- hooks

def _slug(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def _before_save(db: Session, entity: Entity, obj, is_new: bool) -> None:
    if entity.key == "product-masters" and not obj.code:
        obj.code = _generate_product_code(db, obj)
    if entity.key == "batches":
        if not obj.batch_number:
            from app.services.reference_service import next_reference
            obj.batch_number = next_reference(db, "batch")
        if obj.parent_batch_id is not None and obj.parent_batch_id == obj.id:
            raise MasterDataError("A batch cannot be its own parent.")
    if entity.key == "specifications":
        if (obj.grade_id is None) == (obj.product_master_id is None):
            raise MasterDataError("Set exactly one of Grade or Product for a specification.")
        if obj.min_value is not None and obj.max_value is not None and obj.min_value > obj.max_value:
            raise MasterDataError("Min cannot be greater than Max.")
    if entity.key == "subscription-plans" and obj.code not in ("entry", "mid", "premium"):
        raise MasterDataError("Subscription plan code must be entry, mid or premium (the BRD tier keys).")
    if entity.key == "batch-results":
        batch_service.judge_result(db, obj)


def _after_save(db: Session, entity: Entity, obj) -> None:
    if entity.key == "translations":
        from app.core.translation import invalidate
        invalidate()
    if entity.key == "batch-results":
        batch = obj.batch or db.get(BY_KEY["batches"].model, obj.batch_id)
        db.refresh(batch)
        batch_service.evaluate_batch(db, batch)


def _generate_product_code(db: Session, pm) -> str:
    from app.models.md_classification import Grade, MineralType
    from app.models.md_units import ParticleSize
    mt = db.get(MineralType, pm.mineral_type_id) if pm.mineral_type_id else None
    parts = ["MIN", _slug(pm.chemical_formula or (mt.chemical_formula if mt else "") or (mt.code if mt else "GEN"))[:8]]
    if pm.grade_id:
        g = db.get(Grade, pm.grade_id)
        if g is not None:
            parts.append(str(int(g.purity_min_pct)) if g.purity_min_pct else _slug(g.code.split("-")[-1])[:6])
    if pm.particle_size_id:
        ps = db.get(ParticleSize, pm.particle_size_id)
        if ps is not None:
            parts.append(_slug(ps.code.replace("PS-", ""))[:8])
    base = "-".join(p for p in parts if p)
    code, n = base, 2
    model = type(pm)
    while db.execute(select(model).where(model.code == code, model.id != pm.id)).scalars().first():
        code = f"{base}-{n}"
        n += 1
    return code


# ---------------------------------------------------------------- writes

def _audit(db: Session, actor, action: str, entity: Entity, obj, details: str) -> None:
    if actor is None:
        return
    audit_log_repository.create(db, AuditLog(
        actor_user_id=actor.id, action=action, target_type=entity.key, target_id=obj.id, details=details[:2000],
    ))


def save_row(db: Session, entity: Entity, obj, values: dict, actor) -> object:
    """Create (obj=None) or update. Commits. Raises MasterDataError."""
    is_new = obj is None
    if is_new:
        obj = entity.model()
        if obj.id is None:
            obj.id = uuid.uuid4()
    changes = []
    for name, value in values.items():
        old = getattr(obj, name, None)
        old_cmp = old.value if hasattr(old, "value") else old
        if is_new or old_cmp != value:
            changes.append(f"{name}: {old_cmp!r} → {value!r}" if not is_new else f"{name}={value!r}")
        setattr(obj, name, value)
    try:
        _before_save(db, entity, obj, is_new)
        if is_new:
            db.add(obj)
        db.flush()
        _after_save(db, entity, obj)
        if changes:
            _audit(db, actor, "master_data_created" if is_new else "master_data_updated", entity, obj,
                   f"{entity.title} {label_of(entity, obj)}: " + "; ".join(changes))
        db.commit()
    except MasterDataError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise MasterDataError(_integrity_message(exc, entity))
    db.refresh(obj)
    return obj


def _integrity_message(exc: IntegrityError, entity: Entity) -> str:
    msg = str(exc.orig) if exc.orig else str(exc)
    if "unique" in msg.lower() or "duplicate" in msg.lower():
        return f"A {entity.title} row with the same {' / '.join(entity.natural_key)} already exists."
    if "foreign key" in msg.lower():
        return (f"This {entity.title} row is referenced by other records and can't be removed. "
                "Deactivate it instead — it will disappear from dropdowns but history stays intact.")
    if "check constraint" in msg.lower():
        return "The values break a data rule (e.g. min greater than max, or both grade and product set)."
    return "The database rejected this change: " + msg.splitlines()[0][:200]


def toggle_active(db: Session, entity: Entity, obj, actor) -> object:
    if not entity.has_active:
        raise MasterDataError(f"{entity.title} rows have no active flag.")
    obj.is_active = not obj.is_active
    _audit(db, actor, "master_data_activated" if obj.is_active else "master_data_deactivated", entity, obj,
           f"{entity.title} {label_of(entity, obj)}")
    db.commit()
    return obj


def delete_row(db: Session, entity: Entity, obj, actor) -> None:
    label = label_of(entity, obj)
    obj_id = obj.id
    try:
        batch = obj.batch if entity.key == "batch-results" else None
        db.delete(obj)
        db.flush()
        if batch is not None:
            db.refresh(batch)
            batch_service.evaluate_batch(db, batch)
        audit_log_repository.create(db, AuditLog(
            actor_user_id=actor.id, action="master_data_deleted", target_type=entity.key, target_id=obj_id,
            details=f"{entity.title} {label}",
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MasterDataError(_integrity_message(exc, entity))


# ---------------------------------------------------------------- CSV

def csv_columns(entity: Entity) -> list[str]:
    return [f.name for f in entity.fields]


def export_csv(db: Session, entity: Entity) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    cols = csv_columns(entity)
    writer.writerow(cols)
    query = select(entity.model)
    for col in entity.order_by:
        query = query.order_by(getattr(entity.model, col))
    for obj in db.execute(query).scalars().all():
        row = []
        for f in entity.fields:
            value = getattr(obj, f.name, None)
            if f.type == "fk" and value is not None:
                target = BY_KEY[f.fk]
                ref = db.get(target.model, value)
                row.append(natural_key_str(db, target, ref) if ref else "")
            elif hasattr(value, "value"):
                row.append(value.value)
            elif isinstance(value, bool):
                row.append("true" if value else "false")
            elif isinstance(value, Decimal):
                row.append(f"{value.normalize():f}")
            else:
                row.append("" if value is None else str(value))
        writer.writerow(row)
    return buf.getvalue()


def upsert_records(db: Session, entity: Entity, records: list[dict], actor=None) -> ImportResult:
    """Upsert by natural key. Each record is {column: text}. FK columns hold the
    target's natural key (e.g. a code). One bad row never blocks the others:
    each row runs in its own SAVEPOINT."""
    result = ImportResult()
    for i, record in enumerate(records, start=2):  # row 1 = header in a CSV
        record = {k.strip(): (v if v is not None else "") for k, v in record.items() if k}
        try:
            with db.begin_nested():
                values, errors = parse_values(db, entity, record, from_csv=True, only_present=True)
                if errors:
                    raise MasterDataError("; ".join(errors))
                probe = entity.model()
                for name in entity.natural_key:
                    setattr(probe, name, values.get(name))
                existing = None
                if all(values.get(n) is not None or n in ("grade_id", "product_master_id") for n in entity.natural_key):
                    q = select(entity.model)
                    for n in entity.natural_key:
                        q = q.where(getattr(entity.model, n) == values.get(n)) if values.get(n) is not None \
                            else q.where(getattr(entity.model, n).is_(None))
                    existing = db.execute(q).scalars().first()
                obj = existing or entity.model()
                if existing is None and obj.id is None:
                    obj.id = uuid.uuid4()
                for name, value in values.items():
                    setattr(obj, name, value)
                if existing is None:
                    for f in entity.fields:  # apply column defaults for columns absent from the CSV
                        if f.name not in values and getattr(obj, f.name, None) is None:
                            default = column_default(entity, f.name)
                            if default is not None:
                                setattr(obj, f.name, default)
                _before_save(db, entity, obj, existing is None)
                if existing is None:
                    db.add(obj)
                db.flush()
                _after_save(db, entity, obj)
            if existing is None:
                result.created += 1
            else:
                result.updated += 1
        except (MasterDataError, IntegrityError) as exc:
            msg = _integrity_message(exc, entity) if isinstance(exc, IntegrityError) else str(exc)
            result.errors.append(f"Row {i}: {msg}")
    if actor is not None and (result.created or result.updated):
        audit_log_repository.create(db, AuditLog(
            actor_user_id=actor.id, action="master_data_imported", target_type=entity.key, target_id=actor.id,
            details=f"{entity.title}: {result.created} created, {result.updated} updated, {len(result.errors)} errors",
        ))
    db.commit()
    return result


def import_csv(db: Session, entity: Entity, text: str, actor) -> ImportResult:
    text = text.lstrip("﻿")  # Excel UTF-8 BOM
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise MasterDataError("The file is empty or has no header row.")
    unknown = [c for c in reader.fieldnames if c and c.strip() not in csv_columns(entity)]
    if unknown:
        raise MasterDataError(f"Unknown column(s): {', '.join(unknown)}. Download the template to see valid columns.")
    missing_key = [k for k in entity.natural_key if k not in reader.fieldnames and k not in ("grade_id", "product_master_id")]
    if missing_key:
        raise MasterDataError(f"Missing key column(s): {', '.join(missing_key)}.")
    return upsert_records(db, entity, list(reader), actor)


def entity_stats(db: Session, entity: Entity) -> dict:
    model = entity.model
    total = count_rows(db, entity)
    active = total
    if entity.has_active and hasattr(model, "is_active"):
        active = db.execute(select(func.count()).select_from(model).where(model.is_active.is_(True))).scalar_one()
    last = None
    if hasattr(model, "updated_at"):
        last = db.execute(select(func.max(model.updated_at))).scalar_one()
    return {"total": total, "active": active, "inactive": total - active, "last": last}
