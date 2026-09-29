"""
app/services/document_upload_service.py
"""
import uuid
from pathlib import Path

from fastapi import UploadFile

DOCUMENT_DIR = Path("storage/company_documents")
LEGACY_DOCUMENT_DIR = Path("app/static/uploads/company_documents")
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024  # 5MB — per explicit requirement
ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}


class DocumentUploadError(ValueError):
    pass


def validate_document(file: UploadFile, contents: bytes, *, field_label: str) -> str:
    if file is None or not file.filename:
        raise DocumentUploadError(f"{field_label} is required.")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise DocumentUploadError(f"{field_label} must be a PDF, JPG, or PNG file.")
    if len(contents) > MAX_DOCUMENT_BYTES:
        raise DocumentUploadError(f"{field_label} must be 5MB or smaller.")
    if len(contents) == 0:
        raise DocumentUploadError(f"{field_label} appears to be empty.")
    extension = ALLOWED_CONTENT_TYPES[file.content_type]
    if not contents.startswith(_MAGIC[extension]):
        raise DocumentUploadError(f"{field_label} doesn't look like a real {extension.upper()} file.")
    return extension


_MAGIC = {"pdf": b"%PDF", "png": b"\x89PNG\r\n\x1a\n", "jpg": b"\xff\xd8\xff"}


def resolve_document_path(filename: str) -> Path | None:
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        return None
    for folder in (DOCUMENT_DIR, LEGACY_DOCUMENT_DIR):
        candidate = folder / filename
        if candidate.is_file():
            return candidate
    return None


def migrate_legacy_documents() -> int:
    if not LEGACY_DOCUMENT_DIR.is_dir():
        return 0
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in LEGACY_DOCUMENT_DIR.iterdir():
        if f.is_file() and not f.name.startswith("."):
            f.replace(DOCUMENT_DIR / f.name)
            moved += 1
    return moved


def legacy_public_document_count() -> int:
    if not LEGACY_DOCUMENT_DIR.is_dir():
        return 0
    return sum(1 for f in LEGACY_DOCUMENT_DIR.iterdir() if f.is_file() and not f.name.startswith("."))


def save_company_document(company_id: uuid.UUID, field_name: str, contents: bytes, extension: str) -> str:
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{company_id}-{field_name}-{uuid.uuid4().hex[:8]}.{extension}"
    from app.services import file_crypto
    file_crypto.write(DOCUMENT_DIR / filename, contents)
    return filename
