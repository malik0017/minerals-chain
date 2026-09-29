"""
app/services/master_data/i18n — the Arabic UI catalog (Batch R1).

*.tsv files: one "English<TAB>Arabic" pair per line; "{}" is a wildcard for
a number or data value (e.g. "{} min ago" → "قبل {} دقيقة"). Loaded into the
ui_translations table by load_catalog(); rows an admin already edited in
Master Data → Arabic Translations are NOT overwritten.
"""
from pathlib import Path

from sqlalchemy.orm import Session

HERE = Path(__file__).parent


def read_catalog() -> dict[str, str]:
    out: dict[str, str] = {}
    for f in sorted(HERE.glob("*.tsv")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if "\t" not in line or line.startswith("#"):
                continue
            en, ar = line.split("\t", 1)
            en, ar = " ".join(en.split()), ar.strip()
            if en and ar:
                out[en] = ar
    return out


def load_catalog(db: Session, overwrite: bool = False):
    from app.core.translation import invalidate
    from app.models.ui_translation import UITranslation
    from app.services.master_data.service import ImportResult
    res = ImportResult()
    existing = {t.source_text: t for t in db.query(UITranslation)}
    for en, ar in read_catalog().items():
        row = existing.get(en)
        if row is None:
            db.add(UITranslation(source_text=en, text_ar=ar, context="ui", is_active=True))
            res.created += 1
        elif overwrite and row.text_ar != ar:
            row.text_ar = ar
            res.updated += 1
    db.commit()
    invalidate()
    return res
