"""tests/conftest.py."""
from decimal import Decimal

from app.models.dispute import Dispute, DisputeStatus
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.schemas.quotation import QuotationRequest
from app.schemas.rfq import RFQRequest
from app.services import order_service, quotation_service, rfq_service
from tests.conftest import Client

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _buyer_seller(db):
    buyer = db.query(User).filter_by(email="buyer@mineralstest.com").one()
    seller = db.query(User).filter_by(email="seller@mineralstest.com").one()
    return buyer, seller


def make_order(db, *, confirm=True, deliver=False) -> Order:
    buyer, seller = _buyer_seller(db)
    rfq = rfq_service.create_rfq(db, buyer.company, RFQRequest(
        mineral_type="Iron Ore", quantity_value=Decimal("50"), quantity_unit="MT",
        delivery_location="Jeddah", delivery_timeframe="1 month"), created_by=buyer)
    q = quotation_service.submit_quotation(db, rfq, seller.company, QuotationRequest(
        price_value=Decimal("200"), lead_time_days=7), submitted_by=seller)
    order = order_service.accept_quotation(db, rfq, q, buyer.company)
    if confirm:
        order = order_service.confirm_order(db, order, confirmed_by=seller)
    if deliver:
        order_service.mark_shipped(db, order)
        order = order_service.mark_delivered(db, order)
    return order


def test_cannot_dispute_before_confirmation(db):
    order = make_order(db, confirm=False)
    buyer = Client("buyer@mineralstest.com")
    r = buyer.post("/buyer/disputes/new", {"order_id": str(order.id), "category": "quality",
                                             "reason": "Material is below grade."})
    assert r.status_code == 303 and "error=" in r.headers["location"]
    assert db.query(Dispute).filter_by(order_id=order.id).count() == 0


def test_dispute_full_lifecycle(db, admin):
    order = make_order(db, deliver=True)
    buyer, seller = Client("buyer@mineralstest.com"), Client("seller@mineralstest.com")

    r = buyer.post("/buyer/disputes/new", {"order_id": str(order.id), "category": "quantity",
                                             "reason": "Weighbridge shows 46 MT, not 50 MT.",
                                             "desired_outcome": "Credit for 4 MT"},
                   files={"evidence": ("weighbridge.png", PNG, "image/png")})
    assert r.status_code == 303 and "/buyer/disputes/" in r.headers["location"], r.headers["location"]
    db.expire_all()
    d = db.query(Dispute).filter_by(order_id=order.id).one()
    assert d.status == DisputeStatus.OPEN and d.order.status == OrderStatus.DISPUTED
    assert d.order_status_before == "delivered" and d.messages[0].attachment_hash

    # a second dispute on the same order is refused while one is open
    r = seller.post("/seller/disputes/new", {"order_id": str(order.id), "category": "other", "reason": "Counter claim here"})
    assert "error=" in r.headers["location"]

    # evidence download: the other party can, a stranger can't; the integrity header is set
    f = seller.get(f"/seller/disputes/{d.id}/files/{d.messages[0].id}")
    assert f.status_code == 200 and f.headers["x-integrity"] == "verified"

    # internal note is invisible to parties
    admin.post(f"/admin/disputes/{d.id}/message", {"body": "Check the weighbridge calibration", "internal": "1"})
    page = seller.get(f"/seller/disputes/{d.id}").text
    assert "calibration" not in page
    assert "calibration" in admin.get(f"/admin/disputes/{d.id}").text

    seller.post(f"/seller/disputes/{d.id}/message", {"body": "Loaded 50 MT per our ticket."})
    admin.post(f"/admin/disputes/{d.id}/status", {"status": "under_review"})
    r = admin.post(f"/admin/disputes/{d.id}/decide", {"ruling": "buyer", "decision_text": "Certified weighbridge at delivery prevails."})
    assert "msg=" in r.headers["location"]
    db.expire_all()
    d = db.get(Dispute, d.id)
    assert d.status == DisputeStatus.RESOLVED and d.ruling.value == "buyer"
    assert d.order.status == OrderStatus.RESOLVED and d.order.completed_via_dispute

    # decision is frozen: deciding again fails; correction is logged
    r = admin.post(f"/admin/disputes/{d.id}/decide", {"ruling": "seller", "decision_text": "x" * 30})
    assert "error=" in r.headers["location"]
    admin.post(f"/admin/disputes/{d.id}/correct", {"ruling": "seller", "reason": "Calibration certificate expired"})
    db.expire_all()
    d = db.get(Dispute, d.id)
    assert d.ruling.value == "seller" and len(d.corrections) == 1 and d.corrections[0].previous_ruling == "buyer"


def test_withdraw_restores_order_status(db):
    order = make_order(db)
    seller = Client("seller@mineralstest.com")
    seller.post("/seller/disputes/new", {"order_id": str(order.id), "category": "pricing", "reason": "Buyer disputes agreed price."})
    db.expire_all()
    d = db.query(Dispute).filter_by(order_id=order.id).one()
    buyer = Client("buyer@mineralstest.com")
    r = buyer.post(f"/buyer/disputes/{d.id}/withdraw")  # not the raiser
    assert "error=" in r.headers["location"]
    seller.post(f"/seller/disputes/{d.id}/withdraw")
    db.expire_all()
    d = db.get(Dispute, d.id)
    assert d.status == DisputeStatus.WITHDRAWN and d.order.status == OrderStatus.CONFIRMED


def _product_with_specs(db, name="Limestone (test)"):
    from app.models.product import Product
    from app.schemas.product import ProductRequest
    from app.services import product_service, spec_service
    buyer, seller = _buyer_seller(db)
    p = product_service.create_listing(db, seller.company, ProductRequest(
        mineral_type=name, quantity_value=100, quantity_unit="MT"))
    db.commit()
    spec_service.save_product_specs(db, p, [
        {"parameter": "CaCO3", "min": Decimal("95"), "max": None, "unit": "%", "test_method": "XRF"},
        {"parameter": "SiO2", "min": None, "max": Decimal("2"), "unit": "%", "test_method": "XRF"}])
    db.commit()
    return db.get(Product, p.id)


def _lab_company(db):
    return db.query(User).filter_by(email="lab@mineralstest.com").one().company


def _run_lab(db, measured):
    from app.models.verification import VerificationRequest
    p = _product_with_specs(db)
    seller, lab = Client("seller@mineralstest.com"), Client("lab@mineralstest.com")
    r = seller.post(f"/seller/listings/{p.id}/request-verification", {"lab_company_id": str(_lab_company(db).id)})
    assert r.status_code == 303
    db.expire_all()
    vr = db.query(VerificationRequest).filter_by(product_id=p.id).one()
    # results before testing are refused
    r = lab.post(f"/lab/verification-requests/{vr.id}/results", {"analyst_name": "A"})
    assert "error=" in r.headers["location"]
    lab.post(f"/lab/verification-requests/{vr.id}/schedule", {"collection_date": "2026-10-01", "field_officer": "Khalid"})
    lab.post(f"/lab/verification-requests/{vr.id}/start-testing")
    rows = [("CaCO3", "95", ""), ("SiO2", "", "2")]
    data = {"analyst_name": "Dr. Sara", "notes": "", "spec_pid": ["", ""], "spec_param": [r[0] for r in rows],
            "spec_min": [r[1] for r in rows], "spec_max": [r[2] for r in rows], "spec_unit": ["%", "%"],
            "spec_method": ["XRF", "XRF"], "spec_measured": list(measured)}
    r = lab.post(f"/lab/verification-requests/{vr.id}/results", data)
    assert r.status_code == 303 and "error=" not in r.headers["location"], r.headers["location"]
    db.expire_all()
    return db.get(VerificationRequest, vr.id), lab, seller


def test_lab_results_pass_issue_coa_with_fingerprint(db):
    from app.models.certification import Certification
    from app.services.verification_service import coa_fingerprint
    vr, lab, seller = _run_lab(db, ["97.2", "1.1"])
    assert vr.status.value == "completed" and vr.product.status.value == "verified"
    cert = db.query(Certification).filter_by(verification_request_id=vr.id).one()
    assert cert.all_parameters_pass and len(cert.results) == 2 and cert.certificate_number.startswith("COA-")
    assert cert.file_hash == coa_fingerprint(cert)
    page = seller.get(f"/certificates/{cert.id}").text
    assert "Integrity verified" in page and "PASS" in page
    # buyers may view it; the seller name is masked unless they already have a confirmed order
    # with this seller (the seeded buyer does, so the name is shown)
    buyer_page = Client("buyer@mineralstest.com").get(f"/certificates/{cert.id}")
    assert buyer_page.status_code == 200 and cert.subject_company.company_name in buyer_page.text
    assert lab.get("/lab/certificates").status_code == 200


def test_lab_results_fail_out_of_spec(db):
    vr, _, _ = _run_lab(db, ["93.0", "1.1"])
    assert vr.status.value == "failed" and vr.product.status.value == "failed_verification"
    assert "CaCO3" in vr.rejection_reason


def test_lab_terms_pause_blocks_requests(db, admin):
    from app.models.lab_partner import LabPartnerTerms
    lab = _lab_company(db)
    admin.post(f"/admin/labs/{lab.id}/terms", {"fee_sar": "650", "turnaround_days": "5"})  # accepting unchecked
    p = _product_with_specs(db, "Gypsum (test)")
    r = Client("seller@mineralstest.com").post(f"/seller/listings/{p.id}/request-verification", {"lab_company_id": str(lab.id)})
    assert "error=" in r.headers["location"]
    admin.post(f"/admin/labs/{lab.id}/terms", {"fee_sar": "650", "turnaround_days": "5", "is_accepting_requests": "1"})
    Client("seller@mineralstest.com").post(f"/seller/listings/{p.id}/request-verification", {"lab_company_id": str(lab.id)})
    db.expire_all()
    from app.models.verification import VerificationRequest
    vr = db.query(VerificationRequest).filter_by(product_id=p.id).one()
    assert vr.fee_sar == Decimal("650")
    assert db.query(LabPartnerTerms).filter_by(lab_company_id=lab.id).one().turnaround_days == 5


def _verified_product(db, name, rows):
    from app.models.product import Product, ProductStatus
    p = _product_with_specs(db, name)
    from app.services import spec_service
    spec_service.save_product_specs(db, p, rows)
    p.status = ProductStatus.VERIFIED
    db.commit()
    return db.get(Product, p.id)


def test_structured_rfq_quote_match_revise_compare_and_cancel(db):
    from app.models.quotation import Quotation
    from app.models.rfq import RFQ
    buyer, seller = Client("buyer@mineralstest.com"), Client("seller@mineralstest.com")
    r = buyer.post("/buyer/rfqs", {"mineral_type": "Limestone M3", "quantity_value": "200", "quantity_unit": "MT",
                                   "delivery_location": "Yanbu", "required_by": "2030-01-01", "payment_terms_days": "30",
                                   "spec_param": ["CaCO3", "SiO2"], "spec_min": ["95", ""], "spec_max": ["", "2"],
                                   "spec_unit": ["%", "%"], "spec_method": ["", ""], "spec_pid": ["", ""]})
    assert r.status_code == 303, r.text[:500]
    db.expire_all()
    rfq = db.query(RFQ).filter_by(mineral_type="Limestone M3").order_by(RFQ.created_at.desc()).first()
    assert len(rfq.specs) == 2 and rfq.payment_terms_days == 30 and rfq.delivery_timeframe.startswith("By")

    good = _verified_product(db, "Limestone good", [
        {"parameter": "CaCO3", "min": Decimal("96"), "max": Decimal("99"), "unit": "%", "test_method": None},
        {"parameter": "SiO2", "min": Decimal("0"), "max": Decimal("1.5"), "unit": "%", "test_method": None}])
    r = seller.post(f"/seller/rfq-inbox/{rfq.id}/quote", {"price_value": "150", "lead_time_days": "10",
                                                          "product_id": str(good.id), "validity_days": "14"})
    assert "msg=" in r.headers["location"], r.headers["location"]
    db.expire_all()
    q = db.query(Quotation).filter_by(rfq_id=rfq.id).one()
    assert q.match_score == 100 and q.total_price == Decimal("30000.00") and q.payment_terms_days == 30

    # revise → revision 2 with a new price
    seller.post(f"/seller/rfq-inbox/{rfq.id}/revise", {"price_value": "140", "lead_time_days": "8", "product_id": str(good.id)})
    db.expire_all()
    q = db.get(Quotation, q.id)
    assert q.revision_no == 2 and q.price_value == Decimal("140")

    page = buyer.get(f"/buyer/rfqs/{rfq.id}?sort=match").text
    assert "Best price" in page and "100%" in page

    # cancel closes the RFQ and the open quote
    r = buyer.post(f"/buyer/rfqs/{rfq.id}/cancel", {"reason": "Project postponed"})
    db.expire_all()
    assert db.get(RFQ, rfq.id).status.value == "cancelled" and db.get(Quotation, q.id).status.value == "rejected"


def test_expired_quotation_cannot_be_accepted(db):
    from datetime import date, timedelta
    from app.services.order_service import OrderActionError
    buyer, seller = _buyer_seller(db)
    rfq = rfq_service.create_rfq(db, buyer.company, RFQRequest(
        mineral_type="Kaolin", quantity_value=Decimal("10"), quantity_unit="MT", delivery_location="Dammam",
        delivery_timeframe="soon"), created_by=buyer)
    q = quotation_service.submit_quotation(db, rfq, seller.company, QuotationRequest(price_value=Decimal("5"), lead_time_days=2))
    q.valid_until = date.today() - timedelta(days=1)
    db.commit()
    import pytest
    with pytest.raises(OrderActionError):
        order_service.accept_quotation(db, rfq, q, buyer.company)
    db.rollback()
    from app.core import system_settings as ss
    ss.set_setting(db, "quotation_auto_expire", True, None)
    db.commit()
    assert quotation_service.expire_stale(db) >= 1


def test_admin_suspend_and_reactivate_listing(db, admin):
    p = _verified_product(db, "Feldspar (test)", [])
    admin.post(f"/admin/products/{p.id}/suspend", {"reason": "Complaint under review"})
    db.expire_all()
    from app.models.product import Product
    p = db.get(Product, p.id)
    assert p.status.value == "suspended" and p.status_before_suspension == "verified"
    assert Client("buyer@mineralstest.com").get(f"/buyer/browse/{p.id}").status_code == 303  # hidden from buyers
    admin.post(f"/admin/products/{p.id}/reactivate")
    db.expire_all()
    assert db.get(Product, p.id).status.value == "verified"
    assert admin.get("/admin/products?status=verified").status_code == 200
    assert admin.get("/admin/rfqs").status_code == 200


def test_passport_renewal_window(db, admin):
    from datetime import date, timedelta
    from app.models.certification import Certification, CertificationStatus
    from app.services import certification_service
    p = _verified_product(db, "Barite (renewal test)", [])
    first = certification_service.request_passport(db, p, "domestic")
    certification_service.approve_passport(db, first, admin_user(db))
    import pytest
    with pytest.raises(certification_service.CertificationActionError):
        certification_service.request_passport(db, p, "domestic")   # far from expiry
    first.expiry_date = date.today() + timedelta(days=10)
    db.commit()
    renewal = certification_service.request_passport(db, p, "domestic")
    assert renewal.renewal_of_id == first.id
    certification_service.approve_passport(db, renewal, admin_user(db))
    assert renewal.expiry_date > first.expiry_date + timedelta(days=300)


def admin_user(db):
    return db.query(User).filter_by(email="admin@mineralstest.com").one()

PDF = b"%PDF-1.4 weighbridge ticket\n%%EOF"


def test_documents_invoice_and_receipt(db, admin):
    from app.models.order import OrderDocument
    order = make_order(db, confirm=False)
    buyer, seller = Client("buyer@mineralstest.com"), Client("seller@mineralstest.com")
    # before confirmation: refused
    r = seller.post(f"/seller/orders/{order.id}/documents", {"document_type": "packing_list"},
                    files={"file": ("pl.pdf", PDF, "application/pdf")})
    assert "error=" in r.headers["location"]
    order_service.confirm_order(db, order)
    r = seller.post(f"/seller/orders/{order.id}/documents", {"document_type": "weighbridge_cert", "share": "1"},
                    files={"file": ("wb.pdf", PDF, "application/pdf")})
    assert "msg=" in r.headers["location"], r.headers["location"]
    # a fake PDF (wrong magic bytes) is rejected
    r = buyer.post(f"/buyer/orders/{order.id}/documents", {"document_type": "other"},
                   files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert "error=" in r.headers["location"]
    db.expire_all()
    doc = db.query(OrderDocument).filter_by(order_id=order.id).one()
    d = buyer.get(f"/buyer/orders/{order.id}/documents/{doc.id}")
    assert d.status_code == 200 and d.headers["x-integrity"] == "verified" and d.content == PDF
    assert admin.get(f"/admin/orders/{order.id}/documents/{doc.id}").status_code == 200

    # invoice only after delivery
    r = seller.post(f"/seller/orders/{order.id}/invoice")
    assert "error=" in r.headers["location"]
    db.expire_all()
    o = db.get(Order, order.id)
    order_service.mark_shipped(db, o)
    order_service.mark_delivered(db, o)
    r = seller.post(f"/seller/orders/{order.id}/invoice")
    assert "msg=" in r.headers["location"], r.headers["location"]
    db.expire_all()
    o = db.get(Order, order.id)
    assert o.status == OrderStatus.INVOICED and o.invoice_number.startswith("INV-")
    inv = db.query(OrderDocument).filter_by(order_id=order.id, document_type="invoice").one()
    html = buyer.get(f"/buyer/orders/{order.id}/documents/{inv.id}").text
    assert o.invoice_number in html and "Not a ZATCA e-invoice" in html
    buyer.post(f"/buyer/orders/{order.id}/confirm-receipt")
    db.expire_all()
    assert db.get(Order, order.id).status == OrderStatus.COMPLETED


# ------ regression: approval notifications

def test_register_and_approve_new_company_notifies(db, uniq):
    """Regression (found by the demo-data generator): approve_company passed
    company=… into a helper whose first parameter was also named company."""
    from app.models.notification import Notification
    from app.schemas.auth import RegisterRequest
    from app.services import admin_service, auth_service
    admin = admin_user(db)
    u = auth_service.register_new_company_user(db, RegisterRequest(
        role="buyer", company_name=f"Regression Buyer {uniq}", cr_number=f"77{uniq}01",
        license_or_accreditation_number="IND-1", contact_phone="+966 500000001", full_name="Reg Test",
        email=f"reg{uniq.lower()}@example.com", password="admin123", confirm_password="admin123"),
        cr_document_contents=PDF, cr_document_ext="pdf", license_document_contents=PDF, license_document_ext="pdf",
        consent_version="1.0")
    c = admin_service.approve_company(db, u.company_id, admin)
    assert c.status.value == "approved"
    n = db.query(Notification).filter_by(user_id=u.id, type="registration_approved").one()
    assert n.title_ar and c.company_name in (n.body_ar or "")


def test_arabic_catalog_translates_pages(db):
    from app.core.translation import invalidate, translate_html
    from app.services.master_data.i18n import load_catalog, read_catalog
    assert len(read_catalog()) > 1200
    load_catalog(db)
    invalidate()
    out = translate_html('<html lang="ar"><body><h4>Disputes</h4><span>12 unread</span>'
                         '<input placeholder="Search mineral, grade or name"><script>var x="Disputes"</script></body></html>')
    assert "النزاعات" in out and "12 غير مقروء" in out and "ابحث بالمعدن" in out and 'var x="Disputes"' in out
