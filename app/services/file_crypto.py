"""
app/services/file_crypto.py
"""
from pathlib import Path

from app.core.config import settings

MAGIC = b"MCENC1\n"
ROOTS = (Path("storage"),)


class FileCryptoError(ValueError):
    pass


def _fernet(key: str | None = None):
    key = key if key is not None else settings.FILE_ENCRYPTION_KEY
    if not key:
        return None
    from cryptography.fernet import Fernet
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise FileCryptoError(f"FILE_ENCRYPTION_KEY is invalid: {exc}")


def enabled() -> bool:
    return bool(settings.FILE_ENCRYPTION_KEY)


def is_encrypted(data: bytes) -> bool:
    return data.startswith(MAGIC)


def encrypt(data: bytes, key: str | None = None) -> bytes:
    f = _fernet(key)
    if f is None or is_encrypted(data):
        return data
    return MAGIC + f.encrypt(data)


def decrypt(data: bytes, key: str | None = None) -> bytes:
    if not is_encrypted(data):
        return data
    f = _fernet(key)
    if f is None:
        raise FileCryptoError("File is encrypted but FILE_ENCRYPTION_KEY is not set.")
    from cryptography.fernet import InvalidToken
    try:
        return f.decrypt(data[len(MAGIC):])
    except InvalidToken:
        raise FileCryptoError("File cannot be decrypted with the configured key.")


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypt(data))


def read(path: Path) -> bytes:
    return decrypt(path.read_bytes())


def storage_files():
    for root in ROOTS:
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file() and p.name != ".gitkeep":
                    yield p


def storage_status() -> dict:
    total = enc = 0
    for p in storage_files():
        total += 1
        with p.open("rb") as fh:
            if fh.read(len(MAGIC)) == MAGIC:
                enc += 1
    return {"total": total, "encrypted": enc, "plain": total - enc}


def encrypt_all(key: str | None = None) -> int:
    n = 0
    for p in storage_files():
        data = p.read_bytes()
        if not is_encrypted(data):
            p.write_bytes(encrypt(data, key))
            n += 1
    return n


def rotate(old_key: str, new_key: str) -> int:
    n = 0
    for p in storage_files():
        data = p.read_bytes()
        plain = decrypt(data, old_key) if is_encrypted(data) else data
        p.write_bytes(encrypt(plain, new_key))
        n += 1
    return n


def checklist_item(db) -> dict:
    st = storage_status()
    if not enabled():
        level, detail = "warn", f"Off — {st['total']} private file(s) stored unencrypted."
    elif st["plain"]:
        level, detail = "warn", f"On for new files · {st['plain']} older file(s) still unencrypted."
    else:
        level, detail = "ok", f"AES (Fernet) · {st['encrypted']} file(s) encrypted."
    return {"key": "file_encryption", "level": level, "title": "Uploaded documents encrypted at rest", "detail": detail,
            "fix": "Set FILE_ENCRYPTION_KEY, then run scripts/encrypt_storage.py.",
            "kind": "env" if not enabled() else ("action" if st["plain"] else "none"),
            "env": {} if enabled() else {"FILE_ENCRYPTION_KEY": _new_key()}, "toggle": None,
            "link": "admin_encrypt_storage" if enabled() and st["plain"] else None}


def _new_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()
