"""
app/services/private_files.py
"""
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

STORAGE_ROOT = Path("storage")
MAX_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED = {
    "pdf": ("application/pdf", b"%PDF"),
    "png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    "jpg": ("image/jpeg", b"\xff\xd8\xff"),
    "jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}
GENERATED = {"html": "text/html; charset=utf-8"}


class FileError(ValueError):
    pass


@dataclass
class StoredFile:
    path: str         
    sha256: str
    size: int
    mime: str
    original_name: str


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def save_upload(area: str, filename: str, contents: bytes) -> StoredFile:
    if not filename:
        raise FileError("Choose a file to upload.")
    if not contents:
        raise FileError("The file is empty.")
    if len(contents) > MAX_BYTES:
        raise FileError("Files must be 10 MB or smaller.")
    ext = _ext(filename)
    if ext not in ALLOWED:
        raise FileError("Only PDF, JPG and PNG files are accepted.")
    mime, magic = ALLOWED[ext]
    if magic and not contents.startswith(magic):
        raise FileError(f"This doesn't look like a real {ext.upper()} file.")
    return _write(area, "jpg" if ext == "jpeg" else ext, contents, mime, filename[:255])


def save_generated(area: str, name: str, contents: bytes, ext: str = "html") -> StoredFile:
    """Store a system-generated document (e.g. commercial invoice HTML)."""
    return _write(area, ext, contents, GENERATED.get(ext, "application/octet-stream"), name)


def _write(area: str, ext: str, contents: bytes, mime: str, original: str) -> StoredFile:
    folder = STORAGE_ROOT / area
    folder.mkdir(parents=True, exist_ok=True)
    rel = f"{area}/{uuid.uuid4().hex}.{ext}"
    (STORAGE_ROOT / rel).write_bytes(contents)
    return StoredFile(rel, hashlib.sha256(contents).hexdigest(), len(contents), mime, original)


def resolve(rel_path: str | None) -> Path | None:
    """Absolute path of a stored file, or None (with a traversal guard)."""
    if not rel_path or ".." in rel_path or rel_path.startswith("/") or "\\" in rel_path:
        return None
    p = STORAGE_ROOT / rel_path
    return p if p.is_file() else None


def read_verified(rel_path: str | None, expected_sha256: str | None) -> tuple[bytes, bool]:
    """Returns (contents, intact). intact=False means the file was changed
    after upload — callers still serve it but flag it, and log it."""
    p = resolve(rel_path)
    if p is None:
        raise FileError("File not found.")
    data = p.read_bytes()
    intact = expected_sha256 is None or hashlib.sha256(data).hexdigest() == expected_sha256
    return data, intact


def mime_for(rel_path: str) -> str:
    ext = _ext(rel_path)
    if ext in ALLOWED:
        return ALLOWED[ext][0]
    return GENERATED.get(ext, "application/octet-stream")
