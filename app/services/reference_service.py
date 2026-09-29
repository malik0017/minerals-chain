"""
app/services/reference_service.py
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.system_settings import get_setting
from app.models.document_sequence import DocumentSequence

_PREFIX_SETTING = {
    "rfq": "prefix_rfq",
    "quotation": "prefix_quotation",
    "order": "prefix_order",
    "verification": "prefix_verification",
    "batch": "prefix_batch",
    "invoice": "prefix_invoice",
    "dispute": "prefix_dispute",            
    "data_request": "prefix_data_request",  
    "subscription": "prefix_subscription",  
    "document": "prefix_document",          
    "coa": "prefix_coa",                    
}


def next_reference(db: Session, sequence_key: str) -> str:
    if sequence_key not in _PREFIX_SETTING:
        raise KeyError(f"Unknown sequence: {sequence_key}")
    year = datetime.now(timezone.utc).year
    row = db.execute(
        select(DocumentSequence)
        .where(DocumentSequence.sequence_key == sequence_key, DocumentSequence.year == year)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = DocumentSequence(sequence_key=sequence_key, year=year, last_number=0)
        db.add(row)
        db.flush()
    row.last_number += 1
    db.flush()
    prefix = get_setting(db, _PREFIX_SETTING[sequence_key])
    digits = get_setting(db, "reference_digits")
    return f"{prefix}-{year}-{str(row.last_number).zfill(digits)}"
