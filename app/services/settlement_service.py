"""
app/services/settlement_service.py
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.system_settings import get_setting
from app.models.order import Order, SettlementFee, SettlementFeeStatus

CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def vat_breakdown(db: Session, net: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """(vat_rate_pct, vat_amount, gross) for a net amount at today's VAT setting."""
    rate = Decimal(get_setting(db, "vat_rate_pct"))
    vat = money(net * rate / Decimal(100))
    return rate, vat, money(net + vat)


def snapshot_order_financials(db: Session, order: Order) -> None:
    """Freeze quantity/price/VAT/total on the order at acceptance time."""
    rfq, quotation = order.rfq, order.quotation
    order.quantity = rfq.quantity_value
    order.quantity_unit = rfq.quantity_unit
    order.price_per_unit = quotation.price_value
    order.currency = quotation.price_currency
    order.delivery_location = rfq.delivery_location
    order.required_by = rfq.required_by
    order.payment_terms_days = quotation.payment_terms_days or rfq.payment_terms_days
    order.incoterm_code = (quotation.incoterm or rfq.incoterm).code if (quotation.incoterm or rfq.incoterm) else None
    order.product_id = quotation.product_id
    order.subtotal_sar = money(quotation.price_value * rfq.quantity_value)
    order.vat_rate_pct, order.vat_amount_sar, order.total_value_sar = vat_breakdown(db, order.subtotal_sar)


def create_settlement_fees(db: Session, order: Order) -> list[SettlementFee]:
    if order.settlement_fees:
        return list(order.settlement_fees)
    waive_founders = get_setting(db, "waive_fees_founding_members")
    fees = []
    for party, company, key in (
        ("buyer", order.buyer_company, "settlement_fee_buyer_sar"),
        ("seller", order.seller_company, "settlement_fee_seller_sar"),
    ):
        net = money(get_setting(db, key))
        rate, vat, gross = vat_breakdown(db, net)
        waived = bool(waive_founders and company.is_founding_member) or net == 0
        fee = SettlementFee(
            order_id=order.id, paid_by_company_id=company.id, party=party,
            amount_sar=net, vat_rate_pct=rate, vat_amount_sar=vat, total_sar=gross,
            status=SettlementFeeStatus.WAIVED if waived else SettlementFeeStatus.PENDING,
            gateway="manual",
        )
        db.add(fee)
        fees.append(fee)
        if party == "buyer":
            order.settlement_fee_buyer_sar = net
        else:
            order.settlement_fee_seller_sar = net
    db.flush()
    return fees


def mark_fee(db: Session, fee: SettlementFee, new_status: SettlementFeeStatus, admin, reference: str | None = None) -> SettlementFee:
    if fee.status == new_status:
        return fee
    if fee.status in (SettlementFeeStatus.PAID,) and new_status == SettlementFeeStatus.PENDING:
        raise ValueError("A paid fee can only be refunded, not set back to pending.")
    fee.status = new_status
    fee.recorded_by_user_id = admin.id
    if new_status == SettlementFeeStatus.PAID:
        fee.paid_at = datetime.now(timezone.utc)
        fee.gateway_payment_id = reference or fee.gateway_payment_id
    order = fee.order
    if all(f.status in (SettlementFeeStatus.PAID, SettlementFeeStatus.WAIVED) for f in order.settlement_fees):
        order.settlement_fee_paid_at = order.settlement_fee_paid_at or datetime.now(timezone.utc)
    db.flush()
    return fee
