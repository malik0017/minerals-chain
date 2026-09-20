"""
app/services/document_upload_service.py

Batch B: validates and saves the CR and license/accreditation
documents required at registration. Same shape as
avatar_service.py's save_avatar() — validate type/size, write to a
static folder, return the filename to store — but for PDF/image
business documents instead of profile pictures, and with the
company's own id in the filename (see save_company_document()'s
docstring for why that's safe to do before the company row is
committed).
"""
import uuid
from pathlib import Path

from fastapi import UploadFile

DOCUMENT_DIR = Path("app/static/uploads/company_documents")
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024  # 5MB — per explicit requirement
ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}


class DocumentUploadError(ValueError):
    """Raised for any invalid document upload. Routes catch this and
    show the message."""
    pass


def validate_document(file: UploadFile, contents: bytes, *, field_label: str) -> str:
    """Checks type/size only — does NOT save. Called during form
    validation (before the company row exists) so a bad file is
    rejected with the rest of the form, not after everything else
    already passed. Returns the file extension to use once actually
    saving (see save_company_document())."""
    if file is None or not file.filename:
        raise DocumentUploadError(f"{field_label} is required.")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise DocumentUploadError(f"{field_label} must be a PDF, JPG, or PNG file.")
    if len(contents) > MAX_DOCUMENT_BYTES:
        raise DocumentUploadError(f"{field_label} must be 5MB or smaller.")
    if len(contents) == 0:
        raise DocumentUploadError(f"{field_label} appears to be empty.")
    return ALLOWED_CONTENT_TYPES[file.content_type]


def save_company_document(company_id: uuid.UUID, field_name: str, contents: bytes, extension: str) -> str:
    """Writes the file and returns the filename to store on Company.
    Takes company_id explicitly rather than a Company object — this
    runs BEFORE the company row is committed (registration generates
    the company's UUID up front in auth_service.py specifically so
    this can happen first; see its docstring), so there's no ORM
    object to read an id from yet."""
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{company_id}-{field_name}-{uuid.uuid4().hex[:8]}.{extension}"
    (DOCUMENT_DIR / filename).write_bytes(contents)
    return filename
