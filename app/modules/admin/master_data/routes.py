"""
app/modules/admin/master_data/routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.permissions import require_admin, require_portal
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.user import User, UserRole
from app.services.master_data import service
from app.services.master_data.registry import SECTIONS, get_entity, visible_entities
from app.services.master_data.starter_data import load_starter_data

router = APIRouter(prefix="/admin/master-data", tags=["admin-master-data"])

PAGE_SIZE = 25
MAX_IMPORT_BYTES = 2 * 1024 * 1024  


def _entity_or_404(key: str):
    entity = get_entity(key)
    if entity is None or entity.hidden:
        return None
    return entity


def _redirect(request: Request, name: str, msg: str | None = None, error: str | None = None, **params) -> RedirectResponse:
    url = str(request.url_for(name, **params))
    q = []
    if msg:
        q.append(f"msg={quote(msg)}")
    if error:
        q.append(f"error={quote(error)}")
    return RedirectResponse(url=url + ("?" + "&".join(q) if q else ""), status_code=303)


def _form_context(db: Session, entity, values: dict, obj=None) -> dict:
    fk_options = {}
    for f in entity.fields:
        if f.type == "fk":
            current = getattr(obj, f.name, None) if obj is not None else None
            fk_options[f.name] = service.fk_choices(db, f.fk, include_id=current)
    return {"entity": entity, "values": values, "fk_options": fk_options, "obj": obj}


@router.get("", name="admin_master_data_index")
def index(request: Request, db: Session = Depends(get_db),
          admin: User = Depends(require_admin("master_data")),
          msg: str | None = None, error: str | None = None):
    entities = visible_entities()
    counts = {e.key: service.count_rows(db, e) for e in entities}
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/master-data")
    context.update({
        "sections": [(sid, title, icon, [e for e in entities if e.section == sid]) for sid, title, icon in SECTIONS],
        "counts": counts, "total_rows": sum(counts.values()), "msg": msg, "error": error,
    })
    return templates.TemplateResponse(request, "admin/master_data/index.html", context)


@router.post("/load-starter", name="admin_master_data_load_starter")
def load_starter(request: Request, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin("master_data"))):
    results = load_starter_data(db, actor=admin)
    created = sum(r.created for r in results.values())
    updated = sum(r.updated for r in results.values())
    errors = [f"{k}: {e}" for k, r in results.items() for e in r.errors]
    msg = f"Starter data loaded — {created} created, {updated} refreshed."
    return _redirect(request, "admin_master_data_index", msg=msg, error="; ".join(errors[:5]) if errors else None)


@router.get("/{entity_key}", name="admin_master_data_list")
def list_view(request: Request, entity_key: str, db: Session = Depends(get_db),
              admin: User = Depends(require_admin("master_data")),
              q: str | None = None, active: str | None = None, page: int = 1,
              msg: str | None = None, error: str | None = None):
    entity = _entity_or_404(entity_key)
    if entity is None:
        return _redirect(request, "admin_master_data_index", error="Unknown master data type.")
    page = max(1, page)
    rows, total = service.list_rows(db, entity, q=q, active=active, page=page, page_size=PAGE_SIZE)
    table = [
        {"obj": r, "cells": [service.display_value(db, entity, r, col) for col in entity.list_fields]}
        for r in rows
    ]
    labels = {f.name: f.label for f in entity.fields}
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/master-data")
    context.update({
        "entity": entity, "table": table, "total": total, "page": page,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE), "q": q or "", "active": active or "",
        "columns": [labels.get(c, c) for c in entity.list_fields], "list_fields": entity.list_fields,
        "msg": msg, "error": error, "csv_columns": service.csv_columns(entity),
    })
    return templates.TemplateResponse(request, "admin/master_data/list.html", context)


@router.get("/{entity_key}/export.csv", name="admin_master_data_export")
def export(entity_key: str, db: Session = Depends(get_db),
           admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    if entity is None:
        return Response(status_code=404)
    body = "﻿" + service.export_csv(db, entity)  # BOM so Excel opens Arabic correctly
    return Response(content=body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{entity.key}.csv"'})


@router.get("/{entity_key}/template.csv", name="admin_master_data_template")
def template_csv(entity_key: str, admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    if entity is None:
        return Response(status_code=404)
    body = "﻿" + ",".join(service.csv_columns(entity)) + "\n"
    return Response(content=body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{entity.key}-template.csv"'})


@router.post("/{entity_key}/import", name="admin_master_data_import")
def import_view(request: Request, entity_key: str, form: FormData = Depends(form_data), db: Session = Depends(get_db),
                      admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    if entity is None:
        return _redirect(request, "admin_master_data_index", error="Unknown master data type.")
    upload = form.get("file")
    if upload is None or not getattr(upload, "filename", ""):
        return _redirect(request, "admin_master_data_list", error="Choose a CSV file to import.", entity_key=entity_key)
    if not upload.filename.lower().endswith(".csv"):
        return _redirect(request, "admin_master_data_list", error="Only .csv files are accepted.", entity_key=entity_key)
    raw = upload.file.read()
    if len(raw) > MAX_IMPORT_BYTES:
        return _redirect(request, "admin_master_data_list", error="File too large (max 2 MB).", entity_key=entity_key)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _redirect(request, "admin_master_data_list", error="Save the file as CSV UTF-8 and try again.", entity_key=entity_key)
    try:
        result = service.import_csv(db, entity, text, admin)
    except service.MasterDataError as exc:
        return _redirect(request, "admin_master_data_list", error=str(exc), entity_key=entity_key)
    msg = f"Import finished — {result.created} created, {result.updated} updated."
    err = "; ".join(result.errors[:8]) + (f" (+{len(result.errors) - 8} more)" if len(result.errors) > 8 else "")
    return _redirect(request, "admin_master_data_list", msg=msg, error=err or None, entity_key=entity_key)


@router.get("/{entity_key}/new", name="admin_master_data_new")
def new_form(request: Request, entity_key: str, db: Session = Depends(get_db),
             admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    if entity is None:
        return _redirect(request, "admin_master_data_index", error="Unknown master data type.")
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/master-data")
    context.update(_form_context(db, entity, service.form_values(entity)))
    context.update({"mode": "create", "errors": []})
    return templates.TemplateResponse(request, "admin/master_data/form.html", context)


@router.post("/{entity_key}/new", name="admin_master_data_create")
def create(request: Request, entity_key: str, form: FormData = Depends(form_data), db: Session = Depends(get_db),
                 admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    if entity is None:
        return _redirect(request, "admin_master_data_index", error="Unknown master data type.")
    raw = {f.name: form.get(f.name) for f in entity.fields}
    values, errors = service.parse_values(db, entity, raw)
    if not errors:
        try:
            obj = service.save_row(db, entity, None, values, admin)
            if form.get("_after") == "new":
                return _redirect(request, "admin_master_data_new", entity_key=entity_key)
            return _redirect(request, "admin_master_data_list", msg=f"Created {service.label_of(entity, obj)}.",
                             entity_key=entity_key)
        except service.MasterDataError as exc:
            errors = [str(exc)]
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/master-data")
    redisplay = {f.name: (bool(raw.get(f.name)) if f.type == "bool" else (raw.get(f.name) or "")) for f in entity.fields}
    context.update(_form_context(db, entity, redisplay))
    context.update({"mode": "create", "errors": errors})
    return templates.TemplateResponse(request, "admin/master_data/form.html", context, status_code=422)


@router.get("/{entity_key}/{row_id}/edit", name="admin_master_data_edit")
def edit_form(request: Request, entity_key: str, row_id: uuid.UUID, db: Session = Depends(get_db),
              admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    obj = service.get_row(db, entity, row_id) if entity else None
    if obj is None:
        return _redirect(request, "admin_master_data_index", error="Record not found.")
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/master-data")
    context.update(_form_context(db, entity, service.form_values(entity, obj), obj))
    context.update({"mode": "edit", "errors": []})
    return templates.TemplateResponse(request, "admin/master_data/form.html", context)


@router.post("/{entity_key}/{row_id}/edit", name="admin_master_data_update")
def update(request: Request, entity_key: str, row_id: uuid.UUID, form: FormData = Depends(form_data), db: Session = Depends(get_db),
                 admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    obj = service.get_row(db, entity, row_id) if entity else None
    if obj is None:
        return _redirect(request, "admin_master_data_index", error="Record not found.")
    raw = {f.name: form.get(f.name) for f in entity.fields}
    values, errors = service.parse_values(db, entity, raw)
    if not errors:
        try:
            service.save_row(db, entity, obj, values, admin)
            return _redirect(request, "admin_master_data_list", msg=f"Saved {service.label_of(entity, obj)}.",
                             entity_key=entity_key)
        except service.MasterDataError as exc:
            errors = [str(exc)]
            obj = service.get_row(db, entity, row_id)
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/master-data")
    redisplay = {f.name: (bool(raw.get(f.name)) if f.type == "bool" else (raw.get(f.name) or "")) for f in entity.fields}
    context.update(_form_context(db, entity, redisplay, obj))
    context.update({"mode": "edit", "errors": errors})
    return templates.TemplateResponse(request, "admin/master_data/form.html", context, status_code=422)


@router.post("/{entity_key}/{row_id}/toggle", name="admin_master_data_toggle")
def toggle(request: Request, entity_key: str, row_id: uuid.UUID, db: Session = Depends(get_db),
           admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    obj = service.get_row(db, entity, row_id) if entity else None
    if obj is None:
        return _redirect(request, "admin_master_data_index", error="Record not found.")
    try:
        service.toggle_active(db, entity, obj, admin)
    except service.MasterDataError as exc:
        return _redirect(request, "admin_master_data_list", error=str(exc), entity_key=entity_key)
    state = "activated" if obj.is_active else "deactivated"
    return _redirect(request, "admin_master_data_list", msg=f"{service.label_of(entity, obj)} {state}.", entity_key=entity_key)


@router.post("/{entity_key}/{row_id}/delete", name="admin_master_data_delete")
def delete(request: Request, entity_key: str, row_id: uuid.UUID, db: Session = Depends(get_db),
           admin: User = Depends(require_admin("master_data"))):
    entity = _entity_or_404(entity_key)
    obj = service.get_row(db, entity, row_id) if entity else None
    if obj is None:
        return _redirect(request, "admin_master_data_index", error="Record not found.")
    label = service.label_of(entity, obj)
    try:
        service.delete_row(db, entity, obj, admin)
    except service.MasterDataError as exc:
        return _redirect(request, "admin_master_data_list", error=str(exc), entity_key=entity_key)
    return _redirect(request, "admin_master_data_list", msg=f"Deleted {label}.", entity_key=entity_key)
