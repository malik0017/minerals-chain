"""
app/core/identity_guard.py
"""
from app.models.order import Order


def is_identity_revealed(order: Order) -> bool:
    return order.confirmed_at is not None


def counterparty_company(order: Order, viewer_role: str):
    if not is_identity_revealed(order):
        return None
    if viewer_role == "buyer":
        return order.seller_company
    if viewer_role == "seller":
        return order.buyer_company
    raise ValueError(f"Unknown viewer_role: {viewer_role!r}")
