"""
scripts/generate_demo_data.py — realistic demo / UAT data (100+ records per module)
"""
import io
import os
import random
import runpy
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")

from sqlalchemy import text  

import app.models 
from app.core import system_settings as ss  
from app.core.security import hash_password  
from app.database.base import SessionLocal 
from app.models.batch import Batch, BatchQualityResult, BatchStage  
from app.models.certification import Certification, CertificationStatus, CertificationType  
from app.models.company import ApprovalStatus, Company, CompanyRole  
from app.models.data_request import DataRequest  
from app.models.lab_partner import LabPartnerTerms  
from app.models.md_commercial import Incoterm  
from app.models.md_locations import MineSource, Region, Warehouse  
from app.models.md_product import ProductMaster  
from app.models.md_units import UnitOfMeasure  
from app.models.notification import Notification  
from app.models.order import Order, OrderStatus, SettlementFee, SettlementFeeStatus 
from app.models.product import Product, ProductStatus 
from app.models.subscription import SubscriptionCharge  
from app.models.user import User, UserRole  
from app.models.verification import VerificationRequest  
from app.schemas.auth import RegisterRequest  
from app.schemas.product import ProductRequest  
from app.schemas.quotation import QuotationRequest  
from app.schemas.rfq import RFQRequest  
from app.services import (admin_service, auth_service, certification_service, data_request_service,  
                          dispute_service, order_document_service, order_service, product_service,
                          quotation_service, rfq_service, spec_service, subscription_service,
                          verification_service)
from app.services import control_center_service as cc  
from app.services.master_data import batch_service  
from app.services.master_data.starter_data import load_starter_data  
from app.services.reference_service import next_reference  

PASSWORD = "admin123"
R = random.Random(2026)
NOW = datetime.now(timezone.utc)
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + bytes(64)
HASH = None  # argon2 hash of PASSWORD, computed once

# ------------------------------------------------------------------ name pools (fictional)
PLACES = [("Najd", "نجد"), ("Hijaz", "الحجاز"), ("Tihama", "تهامة"), ("Asir", "عسير"), ("Qassim", "القصيم"),
          ("Jubail", "الجبيل"), ("Yanbu", "ينبع"), ("Tabuk", "تبوك"), ("Hail", "حائل"), ("Nafud", "النفود"),
          ("Sarawat", "السروات"), ("Dahna", "الدهناء"), ("Tuwaiq", "طويق"), ("Summan", "الصمان"), ("Harrat", "الحرات"),
          ("Wadi Fatima", "وادي فاطمة"), ("Al Ula", "العلا"), ("Jazan", "جازان"), ("Najran", "نجران"), ("Baha", "الباحة"),
          ("Arar", "عرعر"), ("Sakaka", "سكاكا"), ("Khurais", "خريص"), ("Rimah", "رماح"), ("Afif", "عفيف"),
          ("Duwadimi", "الدوادمي"), ("Bisha", "بيشة"), ("Qurayyat", "القريات"), ("Ras Al Khair", "رأس الخير"), ("Wajh", "الوجه")]
SELLER_SFX = [("Mining Co.", "للتعدين"), ("Minerals Trading", "لتجارة المعادن"), ("Industrial Minerals", "للمعادن الصناعية"),
              ("Quarries", "للمحاجر"), ("Resources", "للموارد"), ("Mineral Industries", "للصناعات التعدينية")]
BUYER_SFX = [("Cement Co.", "للأسمنت"), ("Glass Industries", "لصناعة الزجاج"), ("Ceramics", "للسيراميك"),
             ("Steel Works", "للحديد والصلب"), ("Paints & Coatings", "للدهانات"), ("Chemicals", "للكيماويات"),
             ("Construction Materials", "لمواد البناء"), ("Refractories", "للحراريات")]
LAB_SFX = [("Testing Laboratories", "لمختبرات الفحص"), ("Analytical Labs", "للمختبرات التحليلية"),
           ("Geo-Lab", "للمختبرات الجيولوجية")]
CITIES = ["Riyadh", "Jeddah", "Dammam", "Jubail", "Yanbu", "Makkah", "Madinah", "Tabuk", "Hail", "Abha", "Buraidah",
          "Khobar", "Jazan", "Najran", "Arar"]
FIRST = ["Abdullah", "Mohammed", "Faisal", "Khalid", "Saud", "Turki", "Nasser", "Fahad", "Omar", "Yousef", "Ibrahim",
         "Sultan", "Majed", "Bandar", "Hamad", "Nora", "Sara", "Reem", "Lama", "Hessa", "Maha", "Abeer", "Dana",
         "Latifa", "Hind", "Mona", "Rana", "Waleed", "Ziad", "Hani", "Adel", "Tariq", "Rakan", "Mishal", "Ahmed"]
LAST = ["Al-Harbi", "Al-Otaibi", "Al-Qahtani", "Al-Ghamdi", "Al-Zahrani", "Al-Shammari", "Al-Dosari", "Al-Mutairi",
        "Al-Anazi", "Al-Shehri", "Al-Subaie", "Al-Johani", "Al-Balawi", "Al-Harthi", "Al-Malki", "Al-Amri",
        "Al-Juhani", "Al-Rashidi", "Al-Enezi", "Al-Faifi", "Al-Asmari", "Al-Yami", "Al-Sulami", "Al-Omari"]
JOBS = ["Procurement Manager", "Sales Manager", "Operations Lead", "Quality Engineer", "Logistics Coordinator",
        "Finance Officer", "Commercial Director", "Lab Supervisor", "Plant Manager", "Trading Specialist"]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---- time travel
class Clock:

    META = None

    def __init__(self, db, base: datetime, span: float = 60):
        age = (NOW - base).total_seconds() / 86400
        self.db, self.base, self.marks = db, base, []
        self.factor = min(1.0, max(age - 0.1, 0.01) / span)
        if Clock.META is None:
            Clock.META = _table_meta(db)

    def step(self, offset_days: float = 0):
        self.db.commit()
        self.marks.append((datetime.now(timezone.utc), offset_days))

    def finish(self):
        db = self.db
        db.commit()
        if not self.marks:
            return
        self.marks.sort()
        latest = datetime.now(timezone.utc) - timedelta(minutes=30)
        targets = []
        for wall, off in self.marks:
            t = min(self.base + timedelta(days=off * self.factor), latest)
            targets.append((wall, t))
        w0 = targets[0][0]
        params = {"w0": w0}
        case_ts, case_days = [], []
        for i, (wall, t) in enumerate(reversed(targets)):
            params[f"w{i}_"] = wall
            params[f"t{i}_"] = t
            params[f"d{i}_"] = (t.date() - wall.date()).days
            case_ts.append(f"WHEN {{c}} >= :w{i}_ THEN :t{i}_ + ({{c}} - :w{i}_)")
            case_days.append(f"WHEN {{s}} >= :w{i}_ THEN :d{i}_")
        for table, ts_cols, date_cols, sel in Clock.META:
            if date_cols and sel:
                days = "CASE " + " ".join(x.format(s=sel) for x in case_days) + " ELSE 0 END"
                sets = ", ".join(f"{d} = {d} + ({days})" for d in date_cols)
                db.execute(text(f"UPDATE {table} SET {sets} WHERE {sel} >= :w0"), params)
            for c in ts_cols:
                expr = "CASE " + " ".join(x.format(c=c) for x in case_ts) + f" ELSE {c} END"
                db.execute(text(f"UPDATE {table} SET {c} = {expr} WHERE {c} >= :w0"), params)
        db.commit()
        db.expire_all()


def _table_meta(db):
    skip = {"alembic_version", "system_settings", "document_sequences", "platform_settings"}
    rows = db.execute(text("""SELECT table_name, column_name, data_type FROM information_schema.columns
                              WHERE table_schema='public'""")).all()
    tables = {}
    for t, c, dt in rows:
        if t in skip:
            continue
        e = tables.setdefault(t, {"ts": [], "date": []})
        if dt == "timestamp with time zone":
            e["ts"].append(c)
        elif dt == "date":
            e["date"].append(c)
    meta = []
    for t, e in tables.items():
        if not e["ts"]:
            continue
        sel = "updated_at" if "updated_at" in e["ts"] else ("created_at" if "created_at" in e["ts"] else None)
        ts = [c for c in e["ts"] if c != sel] + ([sel] if sel else [])
        meta.append((t, ts, e["date"], sel))
    return meta


def days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


def upload(name: str, data: bytes = PDF):
    return SimpleNamespace(filename=name, file=io.BytesIO(data))


# ---- helpers
def person(i: int):
    f, l = FIRST[i % len(FIRST)], LAST[(i * 7) % len(LAST)]
    return f"{f} {l}", f.lower(), l.lower().replace("al-", "")


def cr_number(i):
    return f"{R.choice(['10', '40', '20', '11', '59'])}{R.randint(10**7, 10**8 - 1)}"


def vat_number():
    return f"3{R.randint(10**12, 10**13 - 1)}03"


def make_user(db, company, full_name, email, company_role, job, lang):
    u = User(company_id=company.id, full_name=full_name, email=email, hashed_password=HASH,
             role=UserRole(company.role.value), is_active=company.status == ApprovalStatus.APPROVED,
             company_role=company_role, job_title=job, preferred_language=lang,
             phone=f"+966 5{R.randint(10000000, 99999999)}",
             privacy_consent_at=datetime.now(timezone.utc), privacy_consent_version="1.0")
    db.add(u)
    db.flush()
    return u


# ===== phases
def phase_setup(db):
    log("Loading ERP master data (starter set)…")
    load_starter_data(db)
    log("Seeding the canonical test accounts…")
    try:
        runpy.run_path(str(Path(__file__).parent / "seed_test_data.py"), run_name="__main__")
    except SystemExit as exc:  # the seed script ends with sys.exit()
        if exc.code not in (0, None):
            raise
    db.expire_all()
    for key, val in {"enforce_subscription_limits": False, "quotation_auto_expire": True,
                     "require_specs_for_verification": True, "require_invoice_before_completion": False,
                     "dispute_window_days": 30, "allow_impersonation": True, "dev_mode_banner": False}.items():
        try:
            ss.set_setting(db, key, val, None)
        except Exception:
            pass
    db.commit()
    # all demo passwords = admin123 (also the seeded ones)
    db.execute(text("UPDATE users SET hashed_password = :h"), {"h": HASH})
    db.commit()


def phase_plans(db):
    from app.models.md_commercial import SubscriptionPlan
    for code, price in (("entry", 0), ("mid", 12000), ("premium", 36000)):
        p = db.query(SubscriptionPlan).filter_by(code=code).first()
        if p is not None and not p.annual_price_sar:
            p.annual_price_sar = Decimal(price)
    db.commit()


def phase_admins(db):
    log("Admin team (one per permission level)…")
    super_admin = db.query(User).filter_by(email="admin@mineralstest.com").one()
    super_admin.admin_role = "super_admin"
    team = [("Platform Owner", "owner@mineralschain.sa", "super_admin"),
            ("Operations Admin", "ops@mineralschain.sa", "operations"),
            ("Finance Admin", "finance@mineralschain.sa", "finance"),
            ("Compliance Officer", "compliance@mineralschain.sa", "compliance"),
            ("Support Agent", "support@mineralschain.sa", "support")]
    admins = [super_admin]
    for name, email, role in team:
        u = db.query(User).filter_by(email=email).first()
        if u is None:
            u = User(full_name=name, email=email, hashed_password=HASH, role=UserRole.ADMIN, is_active=True,
                     company_role="owner", admin_role=role, job_title=name)
            db.add(u)
        admins.append(u)
    db.commit()
    return admins


def phase_companies(db, admin):
    log("Companies + users (sellers, buyers, labs)…")
    plan = [("seller", 62), ("buyer", 46), ("lab", 14)]
    regions = db.query(Region).all()
    out = {"seller": [], "buyer": [], "lab": []}
    idx = 0
    used = set()
    for role, n in plan:
        for k in range(n):
            idx += 1
            while True:
                p_en, p_ar = R.choice(PLACES)
                sfx = R.choice(SELLER_SFX if role == "seller" else BUYER_SFX if role == "buyer" else LAB_SFX)
                name = f"{p_en} {sfx[0]}"
                if name not in used:
                    used.add(name)
                    break
            name_ar = f"{p_ar} {sfx[1]}"
            slug = "".join(ch for ch in name.lower() if ch.isalnum())[:18]
            if slug in used:
                slug = f"{slug}{idx}"
            used.add(slug)
            full, f, l = person(idx * 3)
            email = f"{f}.{l}@{slug}.com.sa"
            age = int(365 * (1 - R.random() ** 1.6)) if k > 2 else R.randint(330, 365)
            clock = Clock(db, days_ago(max(age, 3)), span=130)
            clock.step(0)
            try:
                user = auth_service.register_new_company_user(
                    db, RegisterRequest(role=role, company_name=name, cr_number=cr_number(idx),
                                        license_or_accreditation_number=f"{'MIN' if role == 'seller' else 'ACC' if role == 'lab' else 'IND'}-{R.randint(10000, 99999)}",
                                        contact_phone=f"+966 1{R.randint(1000000, 9999999)}", full_name=full,
                                        email=email, password=PASSWORD, confirm_password=PASSWORD),
                    cr_document_contents=PDF, cr_document_ext="pdf", license_document_contents=PDF,
                    license_document_ext="pdf", consent_version="1.0")
            except Exception as exc:  # duplicate CR by chance → skip
                db.rollback()
                log(f"  skip {name}: {exc}")
                continue
            c = user.company
            user.hashed_password = HASH
            user.preferred_language = "ar" if R.random() < 0.3 else "en"
            user.job_title = R.choice(JOBS)
            c.company_name_ar = name_ar
            c.city = R.choice(CITIES)
            c.region_id = R.choice(regions).id if regions else None
            c.vat_registration_number = vat_number()
            c.national_address = f"{R.choice('ABCDEFGHJKLMNPRS')}{R.choice('ABCDEFGHJKLMNPRS')}{R.choice('ABCDEFGHJKLMNPRS')}{R.choice('ABCDEFGHJKLMNPRS')}{R.randint(1000, 9999)}"
            c.is_founding_member = age > 300 and R.random() < 0.35
            db.commit()
            roll = R.random()
            clock.step(R.uniform(0.5, 3))
            if roll < 0.08 and k > 3:
                pass  # stays pending — approval queue
            elif roll < 0.12 and k > 3:
                admin_service.reject_company(db, c.id, admin, R.choice([
                    "CR document is not legible — please re-upload a clear copy.",
                    "Licence number does not match the Ministry of Industry register.",
                    "Company activity in the CR does not cover mineral trading."]))
            else:
                admin_service.approve_company(db, c.id, admin)
                if role != "lab":
                    tier = R.choices(["entry", "mid", "premium"], [50, 30, 20])[0]
                    if tier != "entry":
                        clock.step(R.uniform(3, 20))
                        subscription_service.change_plan(db, c, tier, admin, by_admin=True)
                if roll > 0.96 and k > 3:
                    clock.step(R.uniform(40, 120))
                    cc.change_company_status(db, c, ApprovalStatus.SUSPENDED, admin,
                                             "Suspended pending renewal of the mining licence.")
            # extra team members
            clock.step(R.uniform(1, 30))
            for j in range(R.choice([1, 1, 2, 2, 3])):
                full2, f2, l2 = person(idx * 3 + j + 1)
                make_user(db, c, full2, f"{f2}.{l2}{j}@{slug}.com.sa",
                          R.choice(["manager", "operator", "operator", "viewer"]), R.choice(JOBS),
                          "ar" if R.random() < 0.3 else "en")
            db.commit()
            clock.finish()
            out[role].append(c.id)
    # lab partner terms
    for lab_id in out["lab"]:
        lab = db.get(Company, lab_id)
        if lab.status != ApprovalStatus.APPROVED:
            continue
        db.add(LabPartnerTerms(lab_company_id=lab.id, accreditation_body=R.choice(["SAC (ISO/IEC 17025)", "SASO", "IAS"]),
                               accreditation_number=f"SAC-TL-{R.randint(100, 999)}",
                               accreditation_valid_until=date.today() + timedelta(days=R.randint(90, 900)),
                               accreditation_scope="XRF, ICP-OES, LOI, moisture, particle size",
                               fee_sar=Decimal(R.choice([650, 750, 800, 900, 1100])), turnaround_days=R.randint(4, 12),
                               is_accepting_requests=R.random() > 0.08, is_preferred=R.random() < 0.3))
    db.commit()
    return out


def phase_locations(db):
    log("Mine sources + warehouses…")
    regions = db.query(Region).all()
    sellers = db.query(Company).filter_by(role=CompanyRole.SELLER, status=ApprovalStatus.APPROVED).all()
    n = db.query(MineSource).count()
    for i in range(32):
        p_en, p_ar = PLACES[i % len(PLACES)]
        owner = R.choice(sellers)
        db.add(MineSource(code=f"MINE-{n + i + 1:03d}", name_en=f"{p_en} {R.choice(['Quarry', 'Mine', 'Deposit', 'Pit'])} {i + 1}",
                          name_ar=f"منجم {p_ar} {i + 1}", owner_company_id=owner.id, owner_name=owner.company_name,
                          region_id=R.choice(regions).id if regions else None, location=p_en,
                          latitude=Decimal(str(round(R.uniform(17.5, 31.5), 6))),
                          longitude=Decimal(str(round(R.uniform(36.5, 50.0), 6))),
                          license_number=f"MOI-{R.randint(10000, 99999)}",
                          license_expiry=date.today() + timedelta(days=R.randint(-60, 1500)),
                          extraction_method=R.choice(["open_pit", "quarry", "underground"])))
    w = db.query(Warehouse).count()
    for i in range(20):
        owner = R.choice(sellers)
        db.add(Warehouse(code=f"WH-{w + i + 1:03d}", name_en=f"{owner.city or 'Riyadh'} Yard {i + 1}",
                         name_ar=f"مستودع {i + 1}", company_id=owner.id, city=owner.city,
                         region_id=owner.region_id, capacity_mt=Decimal(R.choice([5000, 10000, 25000, 50000]))))
    db.commit()


def _declared_rows(db, pm_id):
    rows = []
    for r in spec_service.catalog_rows(db, pm_id):
        lo, hi = r["min"], r["max"]
        # sellers usually declare a range inside the catalog range
        if lo is not None and hi is not None and hi > lo:
            span = hi - lo
            lo2 = (lo + span * Decimal(str(round(R.uniform(0, 0.3), 2)))).quantize(Decimal("0.01"))
            hi2 = (hi - span * Decimal(str(round(R.uniform(0, 0.3), 2)))).quantize(Decimal("0.01"))
            lo, hi = lo2, max(hi2, lo2)
        rows.append({**r, "min": lo, "max": hi})
    return rows


def _measure(r, ok: bool) -> str:
    lo, hi = r.get("min"), r.get("max")
    lo = Decimal(lo) if lo is not None else None
    hi = Decimal(hi) if hi is not None else None
    if ok:
        if lo is not None and hi is not None:
            v = lo + (hi - lo) * Decimal(str(round(R.uniform(0.15, 0.85), 3)))
        elif lo is not None:
            v = lo * Decimal(str(round(R.uniform(1.005, 1.04), 3)))
        elif hi is not None:
            v = hi * Decimal(str(round(R.uniform(0.3, 0.9), 3)))
        else:
            v = Decimal(str(round(R.uniform(1, 50), 2)))
    else:
        if lo is not None:
            v = lo * Decimal(str(round(R.uniform(0.9, 0.99), 3)))
        elif hi is not None:
            v = hi * Decimal(str(round(R.uniform(1.05, 1.4), 3)))
        else:
            v = Decimal("0")
    return str(v.quantize(Decimal("0.001")))


def phase_listings(db, admin):
    log("Listings → lab verification → COA → passports…")
    pms = [pm for pm in db.query(ProductMaster).filter_by(is_active=True).all() if spec_service.catalog_rows(db, pm.id)]
    incoterms = db.query(Incoterm).all()
    regions = db.query(Region).all()
    sellers = db.query(Company).filter(Company.role == CompanyRole.SELLER,
                                       Company.status.in_([ApprovalStatus.APPROVED, ApprovalStatus.SUSPENDED])).all()
    labs = [c for c in db.query(Company).filter_by(role=CompanyRole.LAB, status=ApprovalStatus.APPROVED)]
    terms = {t.lab_company_id: t for t in db.query(LabPartnerTerms)}
    labs = [l for l in labs if terms.get(l.id) is None or terms[l.id].is_accepting_requests] or labs
    mines = db.query(MineSource).all()
    made = 0
    for i in range(190):
        seller = R.choice(sellers)
        owner = next((u for u in seller.users if u.company_role == "owner"), seller.users[0])
        pm = R.choice(pms)
        start = min(360, max(5, (NOW - seller.created_at).days - 3))
        age = R.uniform(4, start)
        clock = Clock(db, days_ago(age), span=85)
        clock.step(0)
        qty = Decimal(R.choice([500, 1000, 2000, 5000, 10000, 20000]))
        price = Decimal(R.choice([45, 60, 85, 120, 180, 240, 350, 420, 650]))
        p = product_service.create_listing(db, seller, ProductRequest(
            mineral_type=pm.mineral_type.name_en if pm.mineral_type else pm.name_en,
            grade=pm.grade.name_en if pm.grade else None, specifications_notes=pm.description,
            quantity_value=qty, quantity_unit="MT", price_value=price, price_currency="SAR", price_unit="per MT",
            packaging=R.choice(["Bulk", "Jumbo bags 1 MT", "25 kg bags", "Bulk (truck)"]),
            trade_terms=R.choice(["EXW mine", "FOB Jubail", "FCA Riyadh", "DAP buyer plant"]),
            product_master_id=pm.id, name_ar=pm.name_ar, region_id=R.choice(regions).id if regions else None,
            min_order_qty=Decimal(R.choice([50, 100, 250])), incoterm_id=R.choice(incoterms).id if incoterms else None,
            mine_source_id=R.choice(mines).id if mines else None), created_by=owner)
        spec_service.save_product_specs(db, p, _declared_rows(db, pm.id))
        db.commit()
        made += 1
        if seller.status != ApprovalStatus.APPROVED or R.random() < 0.08:
            clock.finish()
            continue  # stays a draft
        lab = R.choice(labs)
        lab_user = lab.users[0]
        clock.step(R.uniform(0.5, 2))
        vr = verification_service.request_verification(db, p, lab, owner)
        # how far through the workflow: recent requests may still be in progress
        stage = 4 if age > 25 else R.choice([1, 2, 3, 4, 4])
        if stage >= 2:
            clock.step(R.uniform(2, 4))
            verification_service.schedule_sample(db, vr, lab_user, (date.today() + timedelta(days=2)).isoformat(),
                                                 R.choice(["Khalid Al-Harbi", "Omar Al-Qahtani", "Fahad Al-Dosari", "Saad Al-Mutairi"]))
        if stage >= 3:
            clock.step(R.uniform(4, 6))
            verification_service.start_testing(db, vr, lab_user)
        if stage >= 4:
            clock.step(R.uniform(7, 14))
            passing = R.random() < 0.82
            rows = spec_service.product_rows(db, p)
            bad = R.randrange(len(rows)) if rows else -1
            for j, r in enumerate(rows):
                r["measured"] = _measure(r, passing or j != bad)
            verification_service.record_results(db, vr, lab_user, rows, lab_user.full_name,
                                                "Sample homogenised and split; results on dry basis.")
            db.refresh(p)
            if p.status == ProductStatus.VERIFIED and R.random() < 0.92:
                clock.step(R.uniform(15, 25))
                cat = R.choices(["domestic", "gcc_export", "international_export"], [55, 30, 15])[0]
                pp = certification_service.request_passport(db, p, cat)
                roll = R.random()
                if roll < 0.82 or age > 60:
                    clock.step(R.uniform(17, 30))
                    if roll < 0.92:
                        certification_service.approve_passport(db, pp, admin)
                    else:
                        certification_service.reject_passport(db, pp, admin, "Origin documents incomplete — upload the mine licence.")
            if p.status == ProductStatus.VERIFIED and R.random() < 0.04:
                clock.step(R.uniform(40, 80))
                from app.services import marketplace_admin_service as mas
                mas.suspend_product(db, p, admin, "Buyer complaint about moisture content — under review.")
        clock.finish()
    log(f"  {made} listings")


def phase_trade(db, admin):
    log("RFQs → quotations → orders → documents → invoices → disputes…")
    buyers = db.query(Company).filter_by(role=CompanyRole.BUYER, status=ApprovalStatus.APPROVED).all()
    incoterms = db.query(Incoterm).all()
    verified = db.query(Product).filter_by(status=ProductStatus.VERIFIED).all()
    by_pm = {}
    for p in verified:
        by_pm.setdefault(p.product_master_id, []).append(p)
    pm_ids = [k for k, v in by_pm.items() if v and k is not None]
    cities = ["Jubail Industrial City", "Yanbu Industrial City", "Riyadh 2nd Industrial City", "Dammam 2nd Industrial City",
              "Jeddah Industrial City", "Ras Al Khair", "Rabigh", "Sudair Industrial City"]
    stats = {"rfq": 0, "quotes": 0, "orders": 0, "disputes": 0}
    dispute_budget = 108
    for i in range(330):
        buyer_c = R.choice(buyers)
        buyer = next((u for u in buyer_c.users if u.is_active), buyer_c.users[0])
        pm_id = R.choice(pm_ids)
        pm = db.get(ProductMaster, pm_id)
        age = R.uniform(2, min(340, max(10, (NOW - buyer_c.created_at).days - 5)))
        clock = Clock(db, days_ago(age), span=72)
        clock.step(0)
        req_rows = [dict(r) for r in spec_service.catalog_rows(db, pm_id)]
        rfq = rfq_service.create_rfq(db, buyer_c, RFQRequest(
            mineral_type=pm.name_en, specifications_notes=R.choice([None, "Moisture below 3% preferred.",
                                                                    "Sampling at loading point by an accredited lab.",
                                                                    "Deliveries in weekly lots."]),
            quantity_value=Decimal(R.choice([100, 200, 300, 500, 800, 1000, 1500, 2500])), quantity_unit="MT",
            delivery_location=R.choice(cities), delivery_timeframe=R.choice(["Within 30 days", "Within 6 weeks", "Q-end"]),
            product_master_id=pm_id, incoterm_id=R.choice(incoterms).id if incoterms else None,
            required_by=date.today() + timedelta(days=R.randint(20, 60)), payment_terms_days=R.choice([0, 15, 30, 45, 60])),
            created_by=buyer, spec_rows=req_rows)
        stats["rfq"] += 1
        candidates = list({p.seller_company_id: p for p in by_pm[pm_id]}.values())
        R.shuffle(candidates)
        quotes = []
        for p in candidates[:R.choice([1, 2, 2, 3, 3, 4])]:
            seller_c = p.seller_company
            if seller_c.status != ApprovalStatus.APPROVED or seller_c.id == buyer_c.id:
                continue
            clock.step(R.uniform(0.5, 5))
            q = quotation_service.submit_quotation(db, rfq, seller_c, QuotationRequest(
                price_value=(p.price_value or Decimal(100)) * Decimal(str(round(R.uniform(0.9, 1.15), 2))),
                lead_time_days=R.randint(5, 30), product_id=p.id, validity_days=R.choice([14, 21, 30]),
                terms_notes=R.choice([None, "Price valid for full quantity only.", "Includes loading at mine.",
                                      "Third-party inspection at buyer's cost."])), submitted_by=seller_c.users[0])
            quotes.append(q)
            stats["quotes"] += 1
            if R.random() < 0.15:
                clock.step(R.uniform(5, 7))
                quotation_service.revise_quotation(db, q, QuotationRequest(
                    price_value=q.price_value * Decimal("0.96"), lead_time_days=q.lead_time_days, product_id=p.id,
                    validity_days=21), seller_c.users[0])
        roll = R.random()
        if not quotes or (roll < 0.06):
            if roll < 0.06:
                clock.step(R.uniform(8, 12))
                rfq_service.cancel_rfq(db, rfq, buyer, R.choice(["Project postponed to next quarter.",
                                                                 "Requirement covered by an existing contract."]))
            clock.finish()
            continue
        if roll > 0.86 and age < 40:
            clock.finish()  # still comparing quotes
            continue
        best = min(quotes, key=lambda q: (-(q.match_score or 0), q.total_price))
        clock.step(R.uniform(8, 11))
        order = order_service.accept_quotation(db, rfq, best, buyer_c)
        stats["orders"] += 1
        seller_user = order.seller_company.users[0]
        # lifecycle depth, older orders are further along
        target = R.choices(["pending", "confirmed", "in_transit", "delivered", "invoiced", "completed", "cancelled"],
                           [3, 4, 5, 6, 7, 71, 4] if age > 45 else [20, 20, 25, 15, 8, 10, 2])[0]
        if target == "cancelled":
            clock.step(R.uniform(10, 12))
            cc.admin_set_order_status(db, order, OrderStatus.CANCELLED, admin, "Buyer withdrew before confirmation (support ticket).")
            clock.finish()
            continue
        if target == "pending":
            clock.finish()
            continue
        clock.step(R.uniform(10, 12.5))
        order_service.confirm_order(db, order, confirmed_by=seller_user)
        fees = list(order.settlement_fees)
        if target != "confirmed":
            clock.step(R.uniform(13, 18))
            order_service.mark_shipped(db, order)
            if R.random() < 0.6:
                order_document_service.upload(db, order, seller_user, "bill_of_lading", upload("waybill.pdf"), "Truck waybill")
        if target in ("delivered", "invoiced", "completed"):
            clock.step(R.uniform(19, 28))
            order_service.mark_delivered(db, order)
            order_document_service.upload(db, order, seller_user, "weighbridge_cert", upload("weighbridge.pdf"),
                                          "Weighbridge ticket — loading")
            if R.random() < 0.7:
                buyer_u = order.buyer_company.users[0]
                order_document_service.upload(db, order, buyer_u, "proof_of_delivery", upload("pod.jpg", b"\xff\xd8\xff" + bytes(64)),
                                              "Signed delivery note")
        if target in ("invoiced", "completed") and R.random() < 0.8:
            clock.step(R.uniform(28, 30))
            order_document_service.issue_invoice(db, order, seller_user)
        if target == "completed":
            clock.step(R.uniform(30, 34))
            order_service.confirm_receipt(db, order)
        # settlement fees
        for f in fees:
            db.refresh(f)
            if f.status == SettlementFeeStatus.PENDING and R.random() < (0.85 if target == "completed" else 0.35):
                clock.step(R.uniform(12, 20))
                cc.set_fee_status(db, f, "paid", admin, f"BANK-{R.randint(100000, 999999)}")
        # disputes
        db.refresh(order)
        if dispute_budget > 0 and order.status in dispute_service.DISPUTABLE | {OrderStatus.COMPLETED} and \
                R.random() < (0.42 if order.status != OrderStatus.CONFIRMED else 0.2):
            dispute_budget -= 1
            stats["disputes"] += 1
            _dispute_story(db, clock, order, admin)
        clock.finish()
        if i % 25 == 0:
            log(f"  … {i} RFQ stories  {stats}")
    log(f"  {stats}")


def _dispute_story(db, clock, order, admin):
    by_buyer = R.random() < 0.75
    raiser = (order.buyer_company if by_buyer else order.seller_company).users[0]
    other = (order.seller_company if by_buyer else order.buyer_company).users[0]
    cat = R.choice(list(dispute_service.CATEGORIES)) if by_buyer else R.choice(["pricing", "documentation", "other"])
    reasons = {
        "quality": "Lab retest at our plant shows the grade below the agreed specification.",
        "quantity": "Weighbridge at delivery shows a shortfall against the invoiced tonnage.",
        "delivery_delay": "Delivery arrived well after the agreed lead time, causing a production stop.",
        "damaged": "Several bags arrived torn and the material was contaminated with moisture.",
        "documentation": "The certificate of origin and weighbridge tickets were not provided.",
        "pricing": "The invoiced unit price differs from the accepted quotation.",
        "other": "The counterparty is not responding to delivery scheduling requests.",
    }
    clock.step(R.uniform(34, 38))
    d = dispute_service.raise_dispute(db, order, raiser, cat, reasons[cat],
                                      R.choice(["Partial refund", "Replacement shipment", "Price adjustment", "Credit note"]),
                                      upload("evidence.png", PNG) if R.random() < 0.6 else None)
    for k in range(R.randint(1, 4)):
        clock.step(R.uniform(38, 45))
        who, party = (other, "seller" if by_buyer else "buyer") if k % 2 == 0 else (raiser, "buyer" if by_buyer else "seller")
        dispute_service.post_message(db, d, who, party, R.choice([
            "Attached our loading records; the material met the spec at dispatch.",
            "We can offer a partial credit if the independent retest confirms the result.",
            "Please share the sample reference so the lab can compare.",
            "Our logistics partner confirms the delay was caused by a port closure.",
            "Additional photos uploaded."]), upload=upload("photo.png", PNG) if R.random() < 0.25 else None)
    outcome = R.choices(["decided", "withdrawn", "review", "open"], [55, 20, 15, 10])[0]
    if outcome == "withdrawn":
        clock.step(R.uniform(45, 50))
        dispute_service.withdraw(db, d, raiser)
        return
    if outcome == "open":
        return
    clock.step(R.uniform(40, 46))
    dispute_service.post_message(db, d, admin, "admin", "Reviewed the evidence and lab data; requesting the loading sample reference.",
                                 internal=R.random() < 0.5)
    dispute_service.set_status(db, d, admin, R.choice(["under_review", "awaiting_info"]))
    if outcome == "review":
        return
    clock.step(R.uniform(50, 60))
    ruling = "buyer" if R.random() < 0.6 else "seller"
    dispute_service.decide(db, d, admin, ruling, {
        "buyer": "Independent evidence supports the buyer's claim. The seller shall issue a credit for the affected quantity.",
        "seller": "The seller's dispatch records and certified weighbridge tickets prevail; the claim is not upheld."}[ruling])
    if R.random() < 0.06:
        clock.step(R.uniform(60, 70))
        dispute_service.correct_ruling(db, d, admin, "seller" if ruling == "buyer" else "buyer", "",
                                       "Late-arriving lab report changed the factual basis of the decision.")


def phase_subscriptions(db, admin):
    log("Subscription upgrades / renewals / charges + lifecycle run…")
    companies = db.query(Company).filter(Company.role != CompanyRole.LAB, Company.status == ApprovalStatus.APPROVED).all()
    for c in companies:
        tier = c.subscription_tier.value if c.subscription_tier else "entry"
        owner = next((u for u in c.users if u.company_role == "owner"), c.users[0])
        age = (NOW - c.created_at).days
        if age < 20:
            continue
        roll = R.random()
        clock = Clock(db, days_ago(R.uniform(3, max(4, age - 10))), span=30)
        clock.step(0)
        try:
            if tier == "entry" and roll < 0.45:
                subscription_service.change_plan(db, c, R.choice(["mid", "mid", "premium"]), owner)
            elif tier == "mid" and roll < 0.35:
                subscription_service.change_plan(db, c, "premium", owner)
            elif tier != "entry" and roll < 0.85:
                subscription_service.renew(db, c, owner)
        except subscription_service.SubscriptionError:
            db.rollback()
        clock.finish()
    for ch in db.query(SubscriptionCharge).filter_by(status="pending"):
        roll = R.random()
        if roll < 0.72:
            ch.status, ch.paid_at = "paid", ch.created_at + timedelta(days=R.randint(1, 20))
        elif roll < 0.8:
            ch.status = "waived"
    db.commit()
    res = subscription_service.run_lifecycle(db)
    log(f"  lifecycle: {res}")


def phase_data_requests(db, admin):
    log("PDPL data-subject requests…")
    users = db.query(User).filter(User.role != UserRole.ADMIN, User.is_active.is_(True)).all()
    R.shuffle(users)
    n = 0
    for u in users:
        if n >= 112:
            break
        clock = Clock(db, days_ago(R.uniform(1, 200)))
        clock.step(0)
        rtype = R.choices(["access", "correction", "deletion", "restriction", "objection"], [40, 30, 12, 10, 8])[0]
        try:
            req = data_request_service.create_request(db, u, rtype, {
                "access": "Please send me a copy of all personal data you hold about me.",
                "correction": "My job title and mobile number are out of date.",
                "deletion": "I left the company — please delete my personal data.",
                "restriction": "Please stop using my phone number for notifications.",
                "objection": "I object to my name appearing on generated invoices."}[rtype])
        except data_request_service.DataRequestError:
            db.rollback()
            clock.finish()
            continue
        n += 1
        roll = R.random()
        if roll < 0.8:
            clock.step(R.uniform(1, 25))
            status = R.choices(["completed", "rejected", "in_progress"], [70, 10, 20])[0]
            data_request_service.update_request(db, req, admin, status, {
                "completed": "Done — your request has been fulfilled. Thank you.",
                "rejected": "We must retain this record for 10 years under the commercial record-keeping rules.",
                "in_progress": "We are working on your request."}[status])
        clock.finish()
    log(f"  {n} requests")


def phase_batches(db, admin):
    log("Production batches + QC results…")
    pms = [pm for pm in db.query(ProductMaster).filter_by(is_active=True) if batch_service.applicable_specs(db, pm.id)]
    sellers = db.query(Company).filter_by(role=CompanyRole.SELLER, status=ApprovalStatus.APPROVED).all()
    whs = db.query(Warehouse).all()
    mines = db.query(MineSource).all()
    mt = db.query(UnitOfMeasure).filter(UnitOfMeasure.code.in_(["MT", "TON", "T"])).first()
    for i in range(122):
        pm = R.choice(pms)
        clock = Clock(db, days_ago(R.uniform(1, 330)))
        clock.step(0)
        seller = R.choice(sellers)
        b = Batch(batch_number=next_reference(db, "batch"), lot_number=f"L{R.randint(1000, 9999)}",
                  source_batch_ref=f"PIT-{R.randint(10, 99)}-{R.randint(100, 999)}", product_master_id=pm.id,
                  company_id=seller.id, mine_source_id=R.choice(mines).id if mines else None,
                  stage=R.choices([BatchStage.FINISHED, BatchStage.PROCESSING, BatchStage.EXTRACTION], [70, 20, 10])[0],
                  production_date=date.today() - timedelta(days=R.randint(0, 5)),
                  quantity=Decimal(R.choice([250, 500, 1000, 2000, 5000])), uom_id=mt.id if mt else None,
                  warehouse_id=R.choice(whs).id if whs else None)
        db.add(b)
        db.flush()
        specs = batch_service.applicable_specs(db, pm.id)
        if R.random() < 0.9:
            passing = R.random() < 0.8
            items = list(specs.items())
            bad = R.randrange(len(items))
            for j, (pid, s) in enumerate(items):
                val = _measure({"min": s.min_value, "max": s.max_value}, passing or j != bad)
                db.add(BatchQualityResult(batch_id=b.id, parameter_id=pid, measured_value=Decimal(val),
                                          tested_at=date.today()))
            db.flush()
            db.refresh(b)
            batch_service.evaluate_batch(db, b, admin)
        db.commit()
        clock.finish()


def phase_notifications(db):
    log("Marking older notifications read…")
    db.execute(text("""UPDATE notifications SET is_read = true
                       WHERE created_at < now() - interval '10 days' AND random() < 0.75"""))
    db.commit()


def summary(db):
    q = lambda sql: db.execute(text(sql)).scalar()  # noqa: E731
    rows = [("companies", "companies"), ("users", "users"), ("subscriptions", "subscriptions"),
            ("subscription_charges", "subscription_charges"), ("lab partner terms", "lab_partner_terms"),
            ("listings", "products"), ("product specs", "product_specs"), ("verification requests", "verification_requests"),
            ("certificates (COA + passports)", "certifications"), ("COA results", "certification_results"),
            ("RFQs", "rfqs"), ("RFQ spec rows", "rfq_specs"), ("quotations", "quotations"), ("orders", "orders"),
            ("settlement fees", "settlement_fees"), ("order documents", "order_documents"), ("disputes", "disputes"),
            ("dispute messages", "dispute_messages"), ("dispute corrections", "dispute_corrections"),
            ("data requests (PDPL)", "data_requests"), ("batches", "batches"), ("batch QC results", "batch_quality_results"),
            ("mine sources", "mine_sources"), ("warehouses", "warehouses"), ("notifications", "notifications"),
            ("audit log entries", "audit_logs")]
    print("\n=== Demo data summary ===")
    for label, table in rows:
        print(f"  {label:<32} {q(f'SELECT count(*) FROM {table}'):>6}")
    print("\n  Password for EVERY account: admin123")
    print("  Admins: admin@mineralstest.com (super), owner@ / ops@ / finance@ / compliance@ / support@mineralschain.sa")
    print("  Portals: seller@ / buyer@ / lab@mineralstest.com — or any company user listed under Admin → Users")


def main():
    global HASH
    t0 = time.time()
    HASH = hash_password(PASSWORD)
    db = SessionLocal()
    try:
        if db.query(Company).count() > 10:
            print("This database already has data. Run on a fresh, migrated database "
                  "(e.g. createdb mc_demo && alembic upgrade head).")
            return 1
        phase_setup(db)
        phase_plans(db)
        admins = phase_admins(db)
        admin = admins[0]
        phase_companies(db, admin)
        phase_locations(db)
        phase_listings(db, admin)
        phase_trade(db, admin)
        phase_subscriptions(db, admin)
        phase_data_requests(db, admins[3])
        phase_batches(db, admin)
        phase_notifications(db)
        # every account (incl. the seeded ones) logs in with admin123
        db.execute(text("UPDATE users SET hashed_password = :h, failed_login_attempts = 0, locked_until = NULL"), {"h": HASH})
        db.commit()
        summary(db)
    finally:
        db.close()
    log(f"Finished in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
