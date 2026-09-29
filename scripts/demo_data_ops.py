"""
scripts/demo_data_ops.py — demo data for the operations release (inventory, logistics, documents, …)
"""
from datetime import timedelta
from decimal import Decimal

from app.models.company import ApprovalStatus, Company, CompanyRole
from app.models.md_locations import Warehouse
from app.models.product import Product, ProductStatus


def log(msg):
    print(f"  · {msg}", flush=True)


def phase_inventory(db, ctx):
    from app.services import inventory_service as inv
    Clock, R, NOW = ctx["Clock"], ctx["R"], ctx["NOW"]
    sellers = db.query(Company).filter_by(role=CompanyRole.SELLER, status=ApprovalStatus.APPROVED).all()
    n = 0
    for c in sellers:
        whs = inv.warehouses_for(db, c)
        own = [w for w in whs if w.company_id == c.id]
        if not own:
            clock = Clock(db, c.created_at + timedelta(days=2), span=10)
            clock.step(0)
            inv.create_warehouse(db, c, c.users[0], {"name_en": f"{c.city or 'Main'} Stockyard", "city": c.city,
                                                     "capacity_mt": str(R.choice([20000, 50000, 100000]))})
            clock.finish()
            whs = inv.warehouses_for(db, c)
        user = c.users[0]
        for p in db.query(Product).filter(Product.seller_company_id == c.id,
                                          Product.status.in_([ProductStatus.VERIFIED, ProductStatus.UNDER_VERIFICATION])):
            base = p.created_at + timedelta(days=1)
            clock = Clock(db, base, span=40)
            wh = R.choice(whs)
            for k in range(R.randint(1, 3)):
                clock.step(k * R.uniform(5, 12))
                qty = (Decimal(p.quantity_value) * Decimal(str(round(R.uniform(0.6, 1.4), 2)))).quantize(Decimal("1"))
                inv.record_receipt(db, c, user, {"product_id": str(p.id), "warehouse_id": str(wh.id), "quantity": str(qty),
                                                 "unit_cost_sar": str(round(float(p.price_value or 100) * R.uniform(0.55, 0.75), 2)),
                                                 "note": R.choice(["Pit extraction", "Crushing plant output", "Stockpile survey"])})
                n += 1
            if len(whs) > 1 and R.random() < 0.25:
                clock.step(R.uniform(15, 25))
                other = R.choice([w for w in whs if w.id != wh.id])
                inv.record_transfer(db, c, user, {"product_id": str(p.id), "warehouse_id": str(wh.id),
                                                  "to_warehouse_id": str(other.id), "quantity": str(R.choice([100, 250, 500])),
                                                  "note": "Move to port yard"})
                n += 2
            if R.random() < 0.3:
                clock.step(R.uniform(20, 35))
                inv.record_adjustment(db, c, user, {"product_id": str(p.id), "warehouse_id": str(wh.id),
                                                    "quantity": str(-R.choice([2, 5, 12, 20])),
                                                    "note": R.choice(["Moisture loss after rain", "Physical count variance", "Spillage during loading"])})
                n += 1
            clock.finish()
    log(f"{n} stock movements")


CARRIERS = [("Almajdouie Logistics", "truck"), ("Hala Transport", "truck"), ("Naqel Express", "truck"),
            ("SAR Freight Rail", "rail"), ("Bahri Logistics", "sea"), ("Mosanada Logistics", "multimodal")]
CHECKPOINTS = ["Riyadh ring road weigh station", "Al Khurmah checkpoint", "Qassim junction", "Ras Al-Khair gate",
               "Jubail industrial gate", "Yanbu port gate", "Hail bypass"]
DRIVERS = ["Faisal Al-Harbi", "Saeed Al-Qahtani", "Majed Al-Otaibi", "Nasser Al-Dosari", "Imran Khan", "Rashid Al-Mutairi"]


def phase_shipments(db, ctx):
    from app.models.order import Order
    from app.models.shipment import Shipment, ShipmentEvent
    from app.services import reference_service
    R, NOW = ctx["R"], ctx["NOW"]
    n = 0
    orders = db.query(Order).filter(Order.shipped_at.isnot(None)).order_by(Order.shipped_at).all()
    for o in orders:
        if db.query(Shipment).filter(Shipment.order_id == o.id).first():
            continue
        carrier, mode = R.choice(CARRIERS)
        qty = float(o.quantity or (o.rfq.quantity_value if o.rfq else 100) or 100)
        tare = round(R.uniform(14, 18), 3) if mode == "truck" else round(R.uniform(20, 30), 3)
        gross = round(tare + min(qty, 40 if mode == "truck" else qty), 3)
        start = o.shipped_at
        end = o.delivered_at
        eta = start + timedelta(days=R.choice([2, 3, 4, 6]))
        seller = o.seller_company
        s = Shipment(reference=reference_service.next_reference(db, "shipment"), order_id=o.id,
                     seller_company_id=o.seller_company_id, buyer_company_id=o.buyer_company_id,
                     status="delivered" if end else R.choice(["in_transit", "in_transit", "at_checkpoint", "delayed", "arrived"]),
                     transport_mode=mode, carrier_name=carrier, tracking_number=f"WB{R.randint(1000000, 9999999)}",
                     vehicle_plate=f"{R.randint(1000, 9999)} {R.choice(['RJA', 'KSD', 'BNA', 'TLH', 'DMH'])}" if mode in ("truck", "multimodal") else None,
                     driver_name=R.choice(DRIVERS) if mode in ("truck", "multimodal") else None,
                     driver_phone=f"+9665{R.randint(10000000, 99999999)}" if mode in ("truck", "multimodal") else None,
                     origin=f"{seller.city or 'Mine'} site", destination=o.delivery_location or (o.rfq.delivery_location if o.rfq else None),
                     weighbridge_ticket=f"WBT-{R.randint(10000, 99999)}", gross_weight_t=Decimal(str(gross)), tare_weight_t=Decimal(str(tare)),
                     received_net_t=Decimal(str(round(gross - tare - R.uniform(0, 0.4), 3))) if end else None,
                     dispatched_at=start, eta=eta, delivered_at=end, created_at=start, updated_at=end or start,
                     created_by_user_id=seller.users[0].id if seller.users else None)
        db.add(s)
        db.flush()
        stop = end or min(NOW, start + timedelta(days=R.uniform(0.5, 3)))
        events = [("dispatched", s.origin, "Loaded and dispatched", start)]
        span = (stop - start).total_seconds()
        for k in range(R.randint(1, 3)):
            events.append((R.choice(["in_transit", "at_checkpoint"]), R.choice(CHECKPOINTS), None,
                           start + timedelta(seconds=span * (k + 1) / 5)))
        if not end and s.status in ("delayed", "arrived"):
            events.append((s.status, s.destination if s.status == "arrived" else R.choice(CHECKPOINTS),
                            "Queue at gate" if s.status == "delayed" else None, stop))
        if end:
            events.append(("arrived", s.destination, None, end - timedelta(hours=R.uniform(1, 6))))
            events.append(("delivered", s.destination, "Unloaded, weighbridge out", end))
        for st, loc, note, at in events:
            db.add(ShipmentEvent(shipment_id=s.id, status=st, location=loc, note=note, occurred_at=at, created_at=at, updated_at=at))
        n += 1
    db.commit()
    log(f"{n} shipments")


def phase_documents(db, ctx):
    from datetime import date
    from app.models.company_document import CompanyDocument
    from app.services import company_document_service as docs, private_files
    R, NOW, PDF, admin = ctx["R"], ctx["NOW"], ctx["PDF"], ctx["admin"]
    today = NOW.date()
    n = 0
    for c in db.query(Company).filter(Company.status == ApprovalStatus.APPROVED).all():
        have = {d.doc_type for d in docs.current(db, c)}
        wanted = [t for t in docs.REQUIRED.get(c.role, ()) if t not in have]
        wanted += R.sample(["gosi_cert", "saudization_cert", "chamber_cert", "iso_cert", "insurance", "bank_letter"], R.randint(0, 3))
        for t in wanted:
            if R.random() < 0.12:
                continue
            versions = 2 if R.random() < 0.2 else 1
            for v in range(1, versions + 1):
                issued = today - timedelta(days=R.randint(200, 700) - (v - 1) * 180)
                roll = R.random()
                expires = None if t in ("national_address", "bank_letter") else (
                    today + timedelta(days=R.randint(-40, -1)) if roll < 0.08 else
                    today + timedelta(days=R.randint(3, 60)) if roll < 0.25 else
                    today + timedelta(days=R.randint(61, 540)))
                stored = private_files.save_upload("company_library", f"{t}.pdf", PDF)
                last = v == versions
                status = "approved" if not last else R.choices(["approved", "pending", "rejected"], [80, 15, 5])[0]
                at = NOW - timedelta(days=R.randint(1, 30) if last else R.randint(120, 300))
                db.add(CompanyDocument(company_id=c.id, doc_type=t, number=f"{R.randint(1000000000, 9999999999)}",
                                       issued_on=issued, expires_on=expires, version=v, is_current=last, status=status,
                                       review_note="Scan is unreadable — upload a clear copy" if status == "rejected" else None,
                                       reviewed_by_user_id=admin.id if status != "pending" else None,
                                       reviewed_at=at if status != "pending" else None,
                                       file_path=stored.path, file_sha256=stored.sha256, file_size=stored.size, mime=stored.mime,
                                       original_name=f"{t}-v{v}.pdf", uploaded_by_user_id=c.users[0].id if c.users else None,
                                       created_at=at, updated_at=at))
                n += 1
    db.commit()
    log(f"{n} company documents")


def phase_credentials(db, ctx):
    from app.services import credential_check_service as ccs
    admin, R = ctx["admin"], ctx["R"]
    n = 0
    for c in db.query(Company).all():
        for kind in ("cr", "mining_license") if c.role == CompanyRole.SELLER else ("cr",):
            try:
                ccs.run_check(db, c, kind, admin if R.random() < 0.6 else None, commit=False)
                n += 1
            except ccs.CredentialCheckError:
                pass
    db.commit()
    log(f"{n} registry checks")


def before_trade(db, ctx):
    phase_inventory(db, ctx)


def after_trade(db, ctx):
    phase_shipments(db, ctx)
    phase_documents(db, ctx)
    phase_credentials(db, ctx)
