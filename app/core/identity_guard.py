"""
app/core/identity_guard.py

BRD §7 (Business Rules): "Buyer and seller identities must remain
concealed from one another until an order reaches a formally defined
'confirmed' state — this must be enforced at the data-access level,
not solely at the presentation layer."

Every other place in this codebase that conceals identity (buyer
browse, seller RFQ inbox, buyer's quotation comparison) does it simply
by never querying/rendering the other party's company — there's no
"reveal" transition to model because those views never involve an
Order. This module exists because Order is the one place a REVEAL
actually happens, and it needs to happen consistently across every
page that shows order data (buyer order detail, seller order detail,
any future admin/dispute view) rather than being reimplemented — and
potentially gotten wrong — in each template separately.

"At the data-access level, not solely at the presentation layer" is
taken seriously here: is_identity_revealed() is the single function
every route calls to decide whether to even pass the counterparty's
Company object into the template context, not just whether to render
it. A template that never receives the object can't accidentally leak
it through a stray `{{ order.seller_company }}` debug line.
"""
from app.models.order import Order


def is_identity_revealed(order: Order) -> bool:
    """True from the moment the seller confirms the order onward
    (CONFIRMED, IN_TRANSIT, DELIVERED, COMPLETED) — False only while
    PENDING_CONFIRMATION. Keyed off confirmed_at (an explicit
    timestamp) rather than re-deriving from status, so there's one
    unambiguous source of truth for "did the reveal happen and when."
    """
    return order.confirmed_at is not None


def counterparty_company(order: Order, viewer_role: str):
    """
    Returns the OTHER party's Company object if identity has been
    revealed, else None. `viewer_role` is "buyer" or "seller" — which
    side is looking. Routes should use this instead of reaching for
    `order.seller_company` / `order.buyer_company` directly, so the
    concealment rule can never be bypassed by a route that forgets to
    check is_identity_revealed() itself.
    """
    if not is_identity_revealed(order):
        return None
    if viewer_role == "buyer":
        return order.seller_company
    if viewer_role == "seller":
        return order.buyer_company
    raise ValueError(f"Unknown viewer_role: {viewer_role!r}")
