"""
app/core/system_settings.py
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting


@dataclass(frozen=True)
class SettingDef:
    key: str
    category: str
    label: str
    value_type: str            # bool | int | decimal | str | choice
    default: Any
    help: str = ""
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    choices: tuple[str, ...] = field(default_factory=tuple)
    risky_when: Any = None     


CATEGORIES = {
    "fees": ("Fees & Tax (ZATCA)", "bi-cash-coin"),
    "policy": ("Business Policies", "bi-sliders"),
    "numbering": ("Document Numbering", "bi-123"),
    "security": ("Security", "bi-shield-lock"),
    "devtools": ("Development & Testing Tools", "bi-tools"),
}

DEFINITIONS: list[SettingDef] = [
    # --- Fees & tax ---
    SettingDef("vat_rate_pct", "fees", "VAT rate (%)", "decimal", Decimal("15.00"),
               "KSA standard VAT rate applied to order totals and platform fees. Change only if ZATCA changes the statutory rate.",
               Decimal("0"), Decimal("100")),
    SettingDef("lab_verification_fee_sar", "fees", "Lab verification fee (SAR)", "decimal", Decimal("800.00"),
               "Snapshotted onto each new verification request (Schema V1 lab_requests.fee_sar default 800).", Decimal("0"), Decimal("1000000")),
    SettingDef("settlement_fee_buyer_sar", "fees", "Settlement fee — buyer (SAR, excl. VAT)", "decimal", Decimal("500.00"),
               "Charged to the buyer when an order is confirmed (BRD glossary: settlement fee).", Decimal("0"), Decimal("1000000")),
    SettingDef("settlement_fee_seller_sar", "fees", "Settlement fee — seller (SAR, excl. VAT)", "decimal", Decimal("500.00"),
               "Charged to the seller when an order is confirmed.", Decimal("0"), Decimal("1000000")),
    SettingDef("waive_fees_founding_members", "fees", "Waive settlement fees for founding members", "bool", False,
               "Founding-member companies get their settlement fees recorded as WAIVED instead of PENDING."),
    SettingDef("passport_fee_standard_sar", "fees", "Mineral Passport fee — domestic (SAR)", "decimal", Decimal("0.00"),
               "", Decimal("0"), Decimal("1000000")),
    SettingDef("passport_fee_export_sar", "fees", "Mineral Passport fee — GCC / international (SAR)", "decimal", Decimal("0.00"),
               "", Decimal("0"), Decimal("1000000")),

    # --- Policies ---
    SettingDef("passport_validity_days", "policy", "Mineral Passport validity (days)", "int", 365,
               "Replaces the hardcoded 365-day constant (PROJECT_STATUS 'deliberate scope boundaries').", 1, 3650),
    SettingDef("coa_validity_days", "policy", "Lab certificate (COA) validity (days, 0 = no expiry)", "int", 0,
               "0 keeps today's behavior (lab certificates never expire).", 0, 3650),
    SettingDef("quotation_validity_days", "policy", "Default quotation validity (days)", "int", 7,
               "Schema V1 quotations.validity_days default.", 1, 365),
    SettingDef("rfq_open_days", "policy", "RFQ open period (days)", "int", 14,
               "Sets rfqs.closes_at on creation.", 1, 365),
    SettingDef("qc_auto_release", "policy", "Auto-release batches that pass QC", "bool", True,
               "PASS → RELEASED and FAIL → REJECTED automatically. Off = a person releases each batch."),
    SettingDef("enforce_subscription_limits", "policy", "Enforce subscription listing / RFQ limits", "bool", False,
               "BRD §6.11. Off during testing so limits never block a test flow."),
    SettingDef("passport_renewal_window_days", "policy", "Passport renewal window (days before expiry)", "int", 60,
               "Sellers can request a renewal this many days before the current passport expires (BRD §6.4).", 1, 365),
    SettingDef("dispute_window_days", "policy", "Dispute window after completion (days)", "int", 30,
               "How long after an order completes either party may still raise a dispute (BRD §6.7).", 0, 365),
    SettingDef("require_specs_for_verification", "policy", "Require specification rows before lab verification", "bool", True,
               "BRD §6.2: a listing must declare its mineral-specific parameters before a lab can test it."),
    SettingDef("require_invoice_before_completion", "policy", "Require an invoice before the buyer can complete", "bool", False,
               "BRD §6.6 lifecycle delivered → invoiced → completed. Off = buyer may confirm receipt right after delivery."),
    SettingDef("quotation_auto_expire", "policy", "Expire quotations after their validity date", "bool", True,
               "Expired quotations can no longer be accepted."),
    SettingDef("data_request_sla_days", "policy", "PDPL data-request response time (days)", "int", 30,
               "PDPL: respond to access / correction / deletion requests within 30 days.", 1, 90),
    SettingDef("subscription_expiry_notice_days", "policy", "Notify before subscription expiry (days)", "int", 14, "", 1, 90),
    SettingDef("require_catalog_product_on_listing", "policy", "Require a catalog product on new listings", "bool", False,
               "When on, sellers must pick a Product Master item (clean, comparable catalog). Off = free-text allowed."),

    # --- Numbering ---
    SettingDef("prefix_rfq", "numbering", "RFQ prefix", "str", "RFQ"),
    SettingDef("prefix_quotation", "numbering", "Quotation prefix", "str", "QUO"),
    SettingDef("prefix_order", "numbering", "Order prefix", "str", "ORD"),
    SettingDef("prefix_verification", "numbering", "Lab request prefix", "str", "LAB"),
    SettingDef("prefix_batch", "numbering", "Batch / lot prefix", "str", "LOT"),
    SettingDef("prefix_invoice", "numbering", "Invoice prefix (Batch L — ZATCA)", "str", "INV"),
    SettingDef("prefix_dispute", "numbering", "Dispute prefix", "str", "DSP"),
    SettingDef("prefix_data_request", "numbering", "Data request (PDPL) prefix", "str", "DSR"),
    SettingDef("prefix_subscription", "numbering", "Subscription charge prefix", "str", "SUB"),
    SettingDef("prefix_document", "numbering", "Order document prefix", "str", "DOC"),
    SettingDef("prefix_coa", "numbering", "Certificate of Analysis prefix", "str", "COA"),
    SettingDef("reference_digits", "numbering", "Sequence digits", "int", 5, "RFQ-2026-00001 = 5 digits.", 3, 10),

    # --- Security ---
    SettingDef("max_failed_logins", "security", "Failed logins before lockout", "int", 5, "", 3, 20),
    SettingDef("lockout_minutes", "security", "Lockout duration (minutes)", "int", 30, "", 1, 1440),
    SettingDef("enforce_admin_2fa", "security", "Require 2FA for administrators", "bool", False,
               "When on, an admin without 2FA is sent to 2FA setup before any admin page. NCA ECC: MFA for privileged accounts. Turn ON before production.",
               risky_when=False),
    SettingDef("audit_log_retention_days", "security", "Audit log retention (days)", "int", 2190,
               "Informational until the archive job lands (Batch Q). 2190 days ≈ 6 years, aligned with tax record retention.", 365, 7300),

    # --- Dev tools ---
    SettingDef("dev_mode_banner", "devtools", "Show 'TEST ENVIRONMENT' banner", "bool", False,
               "Optional yellow strip on every page reminding users the data is test data. Off by default (client demos)."),
    SettingDef("allow_impersonation", "devtools", "Allow admin 'View as user'", "bool", False,
               "Lets an admin log in as any user to test their portal. Always blocked when APP_ENV=production, and every use is audit-logged.",
               risky_when=True),
]

_BY_KEY = {d.key: d for d in DEFINITIONS}


class SettingValidationError(ValueError):
    pass


def definition(key: str) -> SettingDef:
    if key not in _BY_KEY:
        raise KeyError(f"Unknown system setting: {key}")
    return _BY_KEY[key]


def _parse(d: SettingDef, raw: str) -> Any:
    if d.value_type == "bool":
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if d.value_type == "int":
        return int(raw)
    if d.value_type == "decimal":
        return Decimal(raw)
    return raw


def _serialize(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def validate(key: str, raw: str | None) -> Any:
    """Parse + validate one submitted value; raises SettingValidationError."""
    d = definition(key)
    if d.value_type == "bool":
        return bool(raw) and str(raw).lower() not in ("0", "false", "off", "")
    raw = (raw or "").strip()
    if raw == "":
        raise SettingValidationError(f"{d.label}: a value is required.")
    try:
        value = _parse(d, raw)
    except (ValueError, InvalidOperation):
        raise SettingValidationError(f"{d.label}: '{raw}' is not a valid {d.value_type}.")
    if d.value_type in ("int", "decimal"):
        if d.min_value is not None and value < d.min_value:
            raise SettingValidationError(f"{d.label}: must be at least {d.min_value}.")
        if d.max_value is not None and value > d.max_value:
            raise SettingValidationError(f"{d.label}: must be at most {d.max_value}.")
    if d.value_type == "str":
        if len(value) > 20 or not value.replace("-", "").replace("_", "").isalnum():
            raise SettingValidationError(f"{d.label}: use up to 20 letters/digits (dash/underscore allowed).")
        value = value.upper()
    if d.choices and value not in d.choices:
        raise SettingValidationError(f"{d.label}: must be one of {', '.join(d.choices)}.")
    return value


def get_setting(db: Session, key: str) -> Any:
    d = definition(key)
    row = db.get(SystemSetting, key)
    if row is None:
        return d.default
    try:
        return _parse(d, row.value)
    except (ValueError, InvalidOperation):
        return d.default


def get_all(db: Session) -> dict[str, dict]:
    rows = {r.key: r for r in db.query(SystemSetting).all()}
    out = {}
    for d in DEFINITIONS:
        row = rows.get(d.key)
        value, invalid = d.default, False
        if row is not None:
            try:
                value = _parse(d, row.value)
            except (ValueError, InvalidOperation):
                invalid = True
        out[d.key] = {"def": d, "value": value, "overridden": row is not None, "invalid": invalid,
                      "updated_at": row.updated_at if row else None}
    return out


def set_setting(db: Session, key: str, value: Any, user_id=None) -> tuple[Any, Any]:
    """Returns (old_value, new_value). Caller commits and audit-logs."""
    d = definition(key)
    old = get_setting(db, key)
    row = db.get(SystemSetting, key)
    if value == d.default:
        if row is not None:
            db.delete(row)   # back to default: store nothing
    else:
        if row is None:
            row = SystemSetting(key=key, value=_serialize(value), updated_by_user_id=user_id)
            db.add(row)
        else:
            row.value = _serialize(value)
            row.updated_by_user_id = user_id
            row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return old, value

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 30


def get_setting_cached(key: str) -> Any:
    import time
    from app.database.base import SessionLocal
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    db = SessionLocal()
    try:
        value = get_setting(db, key)
    except Exception:  
        value = definition(key).default
    finally:
        db.close()
    _CACHE[key] = (time.monotonic(), value)
    return value
