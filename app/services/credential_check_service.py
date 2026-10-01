"""
app/services/credential_check_service.py
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from difflib import SequenceMatcher

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyRole
from app.models.credential_check import CHECK_KINDS, CHECK_RESULTS, CredentialCheck
from app.models.user import User

NAME_MATCH_THRESHOLD = 0.72
STOP_WORDS = {"co", "company", "est", "establishment", "llc", "ltd", "limited", "the", "for", "and", "trading", "group",
              "شركة", "مؤسسة", "المحدودة", "للتجارة"}


class CredentialCheckError(ValueError):
    pass


@dataclass
class Lookup:
    found: bool
    name: str | None = None
    status: str | None = None
    active: bool = True
    issued_on: date | None = None
    expires_on: date | None = None
    raw: dict = field(default_factory=dict)
    error: str | None = None


def _norm(name: str | None) -> str:
    s = unicodedata.normalize("NFKD", (name or "").lower())
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(w for w in s.split() if w not in STOP_WORDS)


def name_similarity(a: str | None, b: str | None) -> float:
    x, y = _norm(a), _norm(b)
    if not x or not y:
        return 0.0
    return SequenceMatcher(None, x, y).ratio()


def _parse_date(v) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _pick(d: dict, *paths):
    for p in paths:
        cur = d
        for k in p.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            return cur
    return None


SANDBOX_CASES = {"000": "not_found", "999": "expired", "888": "inactive", "777": "mismatch"}


def sandbox_case(number: str) -> str:
    digits = re.sub(r"\D", "", number or "")
    return SANDBOX_CASES.get(digits[-3:], "verified")


def _sandbox(kind: str, number: str, company: Company) -> Lookup:
    case = sandbox_case(number)
    today = date.today()
    tail = int(re.sub(r"\D", "", number or "0")[-2:] or 0)
    if case == "not_found":
        return Lookup(found=False, raw={"sandbox": True})
    name = company.company_name if case != "mismatch" else f"{company.company_name.split()[0]} Holding Co."
    if case == "expired":
        return Lookup(found=True, name=name, status="Expired", active=False, issued_on=today - timedelta(days=800),
                      expires_on=today - timedelta(days=12), raw={"sandbox": True})
    if case == "inactive":
        return Lookup(found=True, name=name, status="Suspended", active=False, issued_on=today - timedelta(days=400),
                      expires_on=today + timedelta(days=200), raw={"sandbox": True})
    return Lookup(found=True, name=name, status="Active", active=True, issued_on=today - timedelta(days=300 + tail * 4),
                  expires_on=today + timedelta(days=90 + tail * 5), raw={"sandbox": True})


def _wathq_live(number: str) -> Lookup:
    import httpx
    if not settings.WATHQ_API_KEY:
        return Lookup(found=False, error="WATHQ_API_KEY is not set.")
    try:
        r = httpx.get(f"{settings.WATHQ_BASE_URL.rstrip('/')}/fullinfo/{number}",
                      headers={"apiKey": settings.WATHQ_API_KEY, "Accept": "application/json"},
                      timeout=settings.WATHQ_TIMEOUT)
    except httpx.HTTPError as exc:
        return Lookup(found=False, error=f"Wathq unreachable: {exc}")
    if r.status_code == 404:
        return Lookup(found=False, raw={"status_code": 404})
    if r.status_code >= 400:
        return Lookup(found=False, error=f"Wathq HTTP {r.status_code}", raw={"status_code": r.status_code, "body": r.text[:500]})
    data = r.json()
    status = _pick(data, "status.nameEn", "status.name", "crStatus", "status")
    status = str(status) if status is not None else None
    return Lookup(found=True, name=_pick(data, "crName", "name", "crEntityName"), status=status,
                  active=(status or "").lower() in ("active", "نشط", "قائم", "") or _pick(data, "status.id") in (1, "1"),
                  issued_on=_parse_date(_pick(data, "issueDateGregorian", "issueDate", "crIssueDate")),
                  expires_on=_parse_date(_pick(data, "expiryDateGregorian", "expiryDate", "crExpiryDate")), raw=data)


def _mim_live(number: str) -> Lookup:
    import httpx
    if not (settings.MIM_API_URL and settings.MIM_API_KEY):
        return Lookup(found=False, error="MIM_API_URL / MIM_API_KEY are not set.")
    try:
        r = httpx.get(f"{settings.MIM_API_URL.rstrip('/')}/{number}", headers={"Authorization": f"Bearer {settings.MIM_API_KEY}"},
                      timeout=settings.WATHQ_TIMEOUT)
    except httpx.HTTPError as exc:
        return Lookup(found=False, error=f"MIM service unreachable: {exc}")
    if r.status_code == 404:
        return Lookup(found=False, raw={"status_code": 404})
    if r.status_code >= 400:
        return Lookup(found=False, error=f"MIM HTTP {r.status_code}", raw={"status_code": r.status_code})
    data = r.json()
    status = str(_pick(data, "status", "licenseStatus") or "")
    return Lookup(found=True, name=_pick(data, "holderName", "companyName", "name"), status=status or None,
                  active=status.lower() in ("", "active", "valid", "ساري"),
                  issued_on=_parse_date(_pick(data, "issueDate")), expires_on=_parse_date(_pick(data, "expiryDate")), raw=data)


def mode_for(kind: str) -> str:
    m = (settings.WATHQ_MODE if kind == "cr" else settings.MIM_MODE or "sandbox").lower()
    return m if m in ("sandbox", "live", "off") else "sandbox"


def _lookup(kind: str, number: str, company: Company) -> Lookup:
    mode = mode_for(kind)
    if mode == "off":
        raise CredentialCheckError("Credential checks are switched off (WATHQ_MODE / MIM_MODE = off).")
    if mode == "sandbox":
        return _sandbox(kind, number, company)
    return _wathq_live(number) if kind == "cr" else _mim_live(number)


def run_check(db: Session, company: Company, kind: str, user: User | None = None, commit: bool = True) -> CredentialCheck:
    if kind not in CHECK_KINDS:
        raise CredentialCheckError("Unknown check.")
    if kind == "mining_license" and company.role != CompanyRole.SELLER:
        raise CredentialCheckError("Mining licence checks apply to sellers only.")
    number = company.cr_number if kind == "cr" else company.license_or_accreditation_number
    if not number:
        raise CredentialCheckError("No number on file to check.")
    res = _lookup(kind, number, company)
    sim = name_similarity(company.company_name, res.name) if res.found and res.name else None
    if res.error:
        result = "error"
    elif not res.found:
        result = "not_found"
    elif res.expires_on and res.expires_on < date.today():
        result = "expired"
    elif not res.active:
        result = "inactive"
    elif sim is not None and sim < NAME_MATCH_THRESHOLD:
        result = "mismatch"
    else:
        result = "verified"
    check = CredentialCheck(company_id=company.id, kind=kind, provider="wathq" if kind == "cr" else "mim", mode=mode_for(kind),
                            reference_number=number, result=result, name_on_record=(res.name or "")[:255] or None,
                            status_on_record=(res.status or "")[:60] or None, issued_on=res.issued_on, expires_on=res.expires_on,
                            name_match=None if sim is None else sim >= NAME_MATCH_THRESHOLD,
                            message=res.error or (f"Name similarity {sim:.0%}" if sim is not None else None),
                            raw=res.raw or None, checked_by_user_id=user.id if user else None)
    db.add(check)
    if kind == "mining_license" and result == "verified":
        company.license_verified = True
        if res.expires_on:
            company.license_valid_until = res.expires_on
    if user:
        db.add(AuditLog(actor_user_id=user.id, action="credential_check", target_type="company",
                        target_id=company.id, details=f"{kind} {number}: {result} ({check.mode})"))
    if commit:
        db.commit()
    else:
        db.flush()
    return check


def auto_check(db: Session, company: Company) -> list[CredentialCheck]:
    from app.core.system_settings import get_setting
    if not get_setting(db, "credential_auto_check"):
        return []
    out = []
    for kind in ("cr", "mining_license") if company.role == CompanyRole.SELLER else ("cr",):
        try:
            if mode_for(kind) != "off":
                out.append(run_check(db, company, kind, None, commit=False))
        except CredentialCheckError:
            pass
    return out


def run_all(db: Session, user: User, only_unchecked: bool = True) -> dict:
    checked_ids = {r[0] for r in db.query(CredentialCheck.company_id).distinct()}
    counts = {"companies": 0, "checks": 0, "issues": 0, "skipped": 0}
    for company in db.query(Company).order_by(Company.company_name).all():
        if only_unchecked and company.id in checked_ids:
            continue
        counts["companies"] += 1
        for kind in ("cr", "mining_license") if company.role == CompanyRole.SELLER else ("cr",):
            try:
                c = run_check(db, company, kind, user, commit=False)
            except CredentialCheckError:
                counts["skipped"] += 1
                continue
            counts["checks"] += 1
            if c.result != "verified":
                counts["issues"] += 1
    db.commit()
    return counts


def for_company(db: Session, company_id) -> list[CredentialCheck]:
    return (db.query(CredentialCheck).filter(CredentialCheck.company_id == company_id)
            .order_by(CredentialCheck.created_at.desc()).limit(20).all())


def latest_by_kind(checks: list[CredentialCheck]) -> dict:
    out = {}
    for c in checks:
        out.setdefault(c.kind, c)
    return out


def stats(db: Session) -> dict:
    by_result = dict(db.query(CredentialCheck.result, func.count()).group_by(CredentialCheck.result).all())
    by_kind = dict(db.query(CredentialCheck.kind, func.count()).group_by(CredentialCheck.kind).all())
    checked = db.query(func.count(func.distinct(CredentialCheck.company_id))).scalar() or 0
    companies = db.query(Company).count()
    return {"total": sum(by_result.values()), "verified": by_result.get("verified", 0),
            "issues": sum(v for k, v in by_result.items() if k not in ("verified",)),
            "coverage": round(100 * checked / companies) if companies else 0,
            "by_result": [{"name": CHECK_RESULTS.get(k, k), "value": v} for k, v in by_result.items()],
            "by_kind": [{"name": CHECK_KINDS.get(k, k), "value": v} for k, v in by_kind.items()]}


def panel(db: Session, company: Company) -> dict:
    checks = for_company(db, company.id)
    return {"kinds": CHECK_KINDS, "results": CHECK_RESULTS, "latest": latest_by_kind(checks), "history": checks,
            "modes": {k: mode_for(k) for k in CHECK_KINDS}}
