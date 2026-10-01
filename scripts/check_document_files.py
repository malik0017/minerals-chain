"""
scripts/check_document_files.py
"""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os  # noqa: E402

os.chdir(ROOT)

from app.core.config import settings  # noqa: E402
from app.database.base import SessionLocal  # noqa: E402
from app.models.company_document import CompanyDocument  # noqa: E402
from app.services import company_document_service as docs, file_crypto, placeholder_pdf, private_files  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="List company documents whose stored file is missing or unreadable.")
    ap.add_argument("--placeholder", action="store_true", help="development only: write a placeholder PDF for each missing file")
    args = ap.parse_args()
    if args.placeholder and settings.APP_ENV == "production":
        print("Refusing to write placeholder files in production.")
        return 2
    db = SessionLocal()
    missing = 0
    try:
        for d in db.query(CompanyDocument).order_by(CompanyDocument.created_at).all():
            state = docs.file_state(d)
            if state["ok"]:
                continue
            missing += 1
            label = docs.DOC_TYPES.get(d.doc_type, d.doc_type)
            print(f"MISSING  {d.company.company_name} · {label} v{d.version} -> storage/{d.file_path}")
            if args.placeholder:
                data = placeholder_pdf.make(label, [d.company.company_name, f"Number: {d.number or '-'}", f"Version {d.version}"])
                rel = d.file_path if d.file_path.endswith(".pdf") else f"company_library/{d.id.hex}.pdf"
                file_crypto.write(private_files.STORAGE_ROOT / rel, data)
                d.file_path, d.mime, d.file_size = rel, "application/pdf", len(data)
                d.file_sha256 = hashlib.sha256(data).hexdigest()
                print("         placeholder written")
        if args.placeholder:
            db.commit()
    finally:
        db.close()
    print(f"{missing} document(s) without a readable file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
