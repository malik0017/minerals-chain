"""
scripts/seed_test_data.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.base import SessionLocal
from app.core.security import hash_password
from app.models.company import ApprovalStatus, Company, CompanyRole
from app.models.user import User, UserRole
from app.repositories import company_repository, user_repository
from app.schemas.auth import RegisterRequest
from app.schemas.product import ProductRequest
from app.schemas.rfq import RFQRequest
from app.schemas.quotation import QuotationRequest
from app.services import placeholder_pdf
from app.services import (
    admin_service,
    auth_service,
    certification_service,
    order_service,
    product_service,
    quotation_service,
    rfq_service,
    verification_service,
)

PASSWORD = "admin123"
DUMMY_PDF = placeholder_pdf.make("Minerals Chain test document", ["Seeded for local testing"])


def _add_specs(db, product, rows) -> None:
    """Batch M3: declared specification (required before verification by default)."""
    from decimal import Decimal
    from app.services import spec_service
    if not product.specs:
        spec_service.save_product_specs(db, product, [
            {"parameter": n, "min": Decimal(lo) if lo else None, "max": Decimal(hi) if hi else None,
             "unit": u, "test_method": m} for n, lo, hi, u, m in rows])
        db.commit()


def _print(label: str, value: str) -> None:
    print(f"  {label:<28} {value}")


def get_or_create_admin(db) -> User:
    admin = user_repository.get_by_email(db, "admin@mineralstest.com")
    if admin:
        admin.hashed_password = hash_password(PASSWORD)
        admin.failed_login_attempts = 0
        admin.locked_until = None
        admin.is_active = True
        db.commit()
        print("[fix]  admin@mineralstest.com exists — password reset + unlocked")
        return admin
    admin = User(
        company_id=None,
        full_name="Test Admin",
        email="admin@mineralstest.com",
        hashed_password=hash_password(PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    user_repository.create(db, admin)
    db.commit()
    print("[new]  admin@mineralstest.com created")
    return admin


def get_or_create_company_user(
    db, *, role: str, email: str, full_name: str, company_name: str, cr_number: str, approve: bool = True,
    admin: User | None = None,
) -> tuple[User, Company]:
    existing = user_repository.get_by_email(db, email)
    if existing:
        existing.hashed_password = hash_password(PASSWORD)  # keep demo logins on "admin123"
        existing.failed_login_attempts, existing.locked_until = 0, None
        db.commit()
        print(f"[skip] {email} already exists (password reset)")
        return existing, existing.company

    payload = RegisterRequest(
        role=role,
        company_name=company_name,
        cr_number=cr_number,
        license_or_accreditation_number=f"LIC-{cr_number}",
        contact_phone="+966 500000000",
        full_name=full_name,
        email=email,
        password=PASSWORD,
        confirm_password=PASSWORD,
    )
    user = auth_service.register_new_company_user(
        db, payload,
        cr_document_contents=DUMMY_PDF, cr_document_ext="pdf",
        license_document_contents=DUMMY_PDF, license_document_ext="pdf",
    )
    print(f"[new]  {email} registered ({role}, company={company_name})")

    if approve:
        if admin is None:
            raise ValueError("approve=True requires an admin user")
        admin_service.approve_company(db, user.company_id, admin)
        print(f"       -> company approved")

    db.refresh(user)
    return user, user.company


def main() -> None:
    from app.core.config import settings as _s
    if _s.APP_ENV == "production":
        raise SystemExit("Refusing to load test/demo accounts (password admin123) when APP_ENV=production.")
    db = SessionLocal()
    try:
        print("=== Minerals Chain — seeding test data ===\n")

        admin = get_or_create_admin(db)

        seller_user, seller_company = get_or_create_company_user(
            db, role="seller", email="seller@mineralstest.com", full_name="Test Seller",
            company_name="Al-Faisal Minerals Trading", cr_number="1010000001", admin=admin,
        )
        buyer_user, buyer_company = get_or_create_company_user(
            db, role="buyer", email="buyer@mineralstest.com", full_name="Test Buyer",
            company_name="Gulf Industrial Buyers Co.", cr_number="1010000002", admin=admin,
        )
        lab_user, lab_company = get_or_create_company_user(
            db, role="lab", email="lab@mineralstest.com", full_name="Test Lab Analyst",
            company_name="Riyadh Testing Labs", cr_number="1010000003", admin=admin,
        )

        # --- Second, PENDING-only company — keeps the admin approvals
        # queue non-empty even after the three above are approved. ---
        pending_user, pending_company = get_or_create_company_user(
            db, role="seller", email="pending-seller@mineralstest.com", full_name="Pending Seller",
            company_name="Najd Minerals Co. (Pending)", cr_number="1010000009", approve=False,
        )

        # --- Full product lifecycle: listing -> verification -> passport ---
        from app.repositories import product_repository
        products = product_repository.list_for_company(db, seller_company.id)
        product = next((p for p in products if p.mineral_type == "Bauxite (seed)"), None)

        if product is None:
            product = product_service.create_listing(
                db, seller_company,
                ProductRequest(
                    mineral_type="Bauxite (seed)",
                    grade="Grade A",
                    specifications_notes="Seeded test listing — safe to ignore/delete.",
                    quantity_value=5000,
                    quantity_unit="MT",
                    price_value=350,
                    price_currency="SAR",
                    price_unit="per MT",
                    packaging="Bulk",
                    trade_terms="FOB Jubail",
                ),
            )
            db.commit()
            db.refresh(product)
            print(f"[new]  product listing created ({product.mineral_type}, id={product.id})")
        else:
            print(f"[skip] product listing already exists (id={product.id})")
        _add_specs(db, product, [("Al2O3", "48", None, "%", "XRF"), ("SiO2", None, "6", "%", "XRF"), ("Moisture", None, "10", "%", "Gravimetric")])

        from app.models.product import ProductStatus
        if product.status == ProductStatus.DRAFT:
            req = verification_service.request_verification(db, product, lab_company, seller_user)
            db.commit()
            print("       -> verification requested")
            cert = verification_service.issue_certificate(db, req, lab_user, "All parameters within spec (seeded).")
            db.commit()
            print(f"       -> lab certificate issued ({cert.certificate_number}), product now VERIFIED")
            db.refresh(product)

        from app.models.certification import Certification, CertificationType, CertificationStatus
        passport = (
            db.query(Certification)
            .filter(
                Certification.subject_company_id == seller_company.id,
                Certification.cert_type == CertificationType.MINERAL_PASSPORT,
            )
            .first()
        )
        if passport is None and product.status == ProductStatus.VERIFIED:
            passport = certification_service.request_passport(db, product, "domestic")
            print(f"       -> Mineral Passport requested (id={passport.id})")
        if passport is not None and passport.status == CertificationStatus.PENDING:
            passport = certification_service.approve_passport(db, passport, admin)
            print(f"       -> Mineral Passport approved ({passport.certificate_number})")

        # --- A SECOND pending passport request, so /admin/passports has
        # something to actually review too. Needs its own verified product. ---
        second_product = next(
            (p for p in product_repository.list_for_company(db, seller_company.id) if p.mineral_type == "Iron Ore (seed, pending passport)"),
            None,
        )
        if second_product is None:
            second_product = product_service.create_listing(
                db, seller_company,
                ProductRequest(
                    mineral_type="Iron Ore (seed, pending passport)",
                    quantity_value=2000, quantity_unit="MT",
                    price_value=210, price_currency="SAR", price_unit="per MT",
                ),
            )
            db.commit()
            db.refresh(second_product)
            _add_specs(db, second_product, [("Fe", "62", None, "%", "XRF"), ("SiO2", None, "5", "%", "XRF")])
            req2 = verification_service.request_verification(db, second_product, lab_company, seller_user)
            db.commit()
            verification_service.issue_certificate(db, req2, lab_user, "Seeded — pending passport demo.")
            db.commit()
            db.refresh(second_product)
            pending_passport = certification_service.request_passport(db, second_product, "gcc_export")
            print(f"[new]  second product + PENDING passport request created (id={second_product.id})")
        else:
            from app.models.certification import Certification as _Cert, CertificationType as _CT, CertificationStatus as _CS
            pending_passport = (
                db.query(_Cert)
                .filter(_Cert.subject_company_id == seller_company.id, _Cert.cert_type == _CT.MINERAL_PASSPORT, _Cert.status == _CS.PENDING)
                .first()
            )
            print("[skip] second product (pending passport demo) already exists")

        third_product = next(
            (p for p in product_repository.list_for_company(db, seller_company.id) if p.mineral_type == "Silica Sand (seed, pending verification)"),
            None,
        )
        pending_verification_request = None
        if third_product is None:
            third_product = product_service.create_listing(
                db, seller_company,
                ProductRequest(mineral_type="Silica Sand (seed, pending verification)", quantity_value=800, quantity_unit="MT"),
            )
            db.commit()
            db.refresh(third_product)
            _add_specs(db, third_product, [("SiO2", "99", None, "%", "XRF"), ("Fe2O3", None, "0.05", "%", "ICP")])
            pending_verification_request = verification_service.request_verification(db, third_product, lab_company, seller_user)
            db.commit()
            print(f"[new]  third product + PENDING verification request created (id={pending_verification_request.id})")
        else:
            from app.repositories import verification_repository
            pending_verification_request = next(
                (r for r in verification_repository.list_for_product(db, third_product.id) if r.status.value == "requested"),
                None,
            )
            print("[skip] third product (pending verification demo) already exists")

        # --- Full RFQ -> quotation -> order lifecycle ---
        from app.repositories import rfq_repository
        rfqs = rfq_repository.list_for_company(db, buyer_company.id)
        rfq = next((r for r in rfqs if r.mineral_type == "Bauxite (seed RFQ)"), None)
        if rfq is None:
            rfq = rfq_service.create_rfq(
                db, buyer_company,
                RFQRequest(
                    mineral_type="Bauxite (seed RFQ)",
                    specifications_notes="Seeded test RFQ.",
                    quantity_value=1000, quantity_unit="MT",
                    delivery_location="Jubail Industrial City",
                    delivery_timeframe="30 days",
                    commercial_terms_notes="Net 30.",
                ),
            )
            db.commit()
            db.refresh(rfq)
            print(f"[new]  RFQ created (id={rfq.id})")
        else:
            print(f"[skip] RFQ already exists (id={rfq.id})")

        from app.repositories import quotation_repository
        quotation = quotation_repository.get_by_rfq_and_seller(db, rfq.id, seller_company.id)
        if quotation is None and rfq.status.value == "open":
            quotation = quotation_service.submit_quotation(
                db, rfq, seller_company,
                QuotationRequest(price_value=340, price_currency="SAR", price_unit="per MT", lead_time_days=21, terms_notes="Seeded quotation."),
            )
            db.commit()
            db.refresh(quotation)
            print(f"[new]  quotation submitted (id={quotation.id})")
        elif quotation:
            print(f"[skip] quotation already exists (id={quotation.id})")

        from app.repositories import order_repository
        order = None
        if quotation is not None:
            order = order_repository.get_by_quotation_id(db, quotation.id)

        if order is None and quotation is not None and quotation.status.value == "submitted":
            order = order_service.accept_quotation(db, rfq, quotation, buyer_company)
            db.commit()
            db.refresh(order)
            print(f"[new]  order created from accepted quotation (id={order.id})")
        elif order:
            print(f"[skip] order already exists (id={order.id})")

        if order is not None:
            from app.models.order import OrderStatus
            if order.status == OrderStatus.PENDING_CONFIRMATION:
                order = order_service.confirm_order(db, order)
                db.commit()
                print("       -> order confirmed (identities now revealed)")
            if order.status == OrderStatus.CONFIRMED:
                order = order_service.mark_shipped(db, order)
                db.commit()
                print("       -> order marked in_transit")
            if order.status == OrderStatus.IN_TRANSIT:
                order = order_service.mark_delivered(db, order)
                db.commit()
                print("       -> order marked delivered")
            if order.status == OrderStatus.DELIVERED:
                order = order_service.confirm_receipt(db, order)
                db.commit()
                print("       -> buyer confirmed receipt: order COMPLETED")

        rfq2 = next((r for r in rfqs if r.mineral_type == "Copper Concentrate (seed, open)"), None)
        if rfq2 is None:
            rfq2 = rfq_service.create_rfq(
                db, buyer_company,
                RFQRequest(
                    mineral_type="Copper Concentrate (seed, open)",
                    quantity_value=500, quantity_unit="MT",
                    delivery_location="Dammam Port", delivery_timeframe="45 days",
                ),
            )
            db.commit()
            print(f"[new]  second, still-OPEN RFQ created (id={rfq2.id})")
        else:
            print("[skip] second open RFQ already exists")

        print("\n=== Done. Logins (password for all: admin123) ===")
        _print("Admin:", "admin@mineralstest.com")
        _print("Seller (approved):", "seller@mineralstest.com")
        _print("Buyer (approved):", "buyer@mineralstest.com")
        _print("Lab (approved):", "lab@mineralstest.com")
        _print("Seller (pending, for approvals queue):", "pending-seller@mineralstest.com")
        print("\nIDs for reference (also written to seed_ids.json next to this script):")
        ids = {
            "admin_id": str(admin.id),
            "seller_user_id": str(seller_user.id),
            "seller_company_id": str(seller_company.id),
            "buyer_user_id": str(buyer_user.id),
            "buyer_company_id": str(buyer_company.id),
            "lab_user_id": str(lab_user.id),
            "lab_company_id": str(lab_company.id),
            "pending_company_id": str(pending_company.id),
            "product_id": str(product.id),
            "second_product_id": str(second_product.id),
            "third_product_id": str(third_product.id),
            "pending_verification_request_id": str(pending_verification_request.id) if pending_verification_request else None,
            "passport_id": str(passport.id) if passport else None,
            "pending_passport_id": str(pending_passport.id) if pending_passport else None,
            "rfq_id": str(rfq.id),
            "rfq2_id": str(rfq2.id),
            "quotation_id": str(quotation.id) if quotation else None,
            "order_id": str(order.id) if order else None,
        }

        from app.services.master_data.registry import visible_entities
        from app.services.master_data.service import list_rows
        from app.services.master_data.starter_data import load_starter_data
        from app.models.batch import Batch
        load_starter_data(db)
        example_batch = db.query(Batch).filter(Batch.batch_number == "LOT-2026-00125").first()
        ids["batch_id"] = str(example_batch.id) if example_batch else None
        ids["master_row_ids"] = {}
        for entity in visible_entities():
            rows, _ = list_rows(db, entity, page_size=1)
            ids["master_row_ids"][entity.key] = str(rows[0].id) if rows else None

        for k, v in ids.items():
            if k != "master_row_ids":
                _print(k + ":", str(v))

        import json, pathlib
        out_path = pathlib.Path(__file__).parent / "seed_ids.json"
        out_path.write_text(json.dumps(ids, indent=2))
        print(f"\nWritten: {out_path}")

    except Exception as exc:
        db.rollback()
        print(f"\n[ERROR] Seeding failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
