"""Order state machine (ARCHITECTURE.md section 5.4).

    draft -> awaiting_confirmation -> confirmed -> preparing -> out_for_delivery -> delivered
       \\______________ any state before delivered ______________/-> cancelled

Every status change goes through `transition`, which validates the move and
records an OrderEvent. Nothing else should assign `order.status`.
"""

from datetime import UTC, datetime

from kairos.db.models import Order, OrderEvent, OrderItem
from kairos.domain.enums import Actor, OrderStatus
from kairos.domain.pricing import Quote

S = OrderStatus

FORWARD: dict[OrderStatus, OrderStatus] = {
    S.draft: S.awaiting_confirmation,
    S.awaiting_confirmation: S.confirmed,
    S.confirmed: S.preparing,
    S.preparing: S.out_for_delivery,
    S.out_for_delivery: S.delivered,
}

TERMINAL = frozenset({S.delivered, S.cancelled})
OPEN = frozenset(set(S) - TERMINAL)


class InvalidTransition(ValueError):
    pass


def allowed_next(status: OrderStatus) -> frozenset[OrderStatus]:
    if status in TERMINAL:
        return frozenset()
    return frozenset({FORWARD[status], S.cancelled})


def can_transition(from_status: OrderStatus, to_status: OrderStatus) -> bool:
    return to_status in allowed_next(from_status)


def transition(order: Order, to_status: OrderStatus, actor: Actor,
               at: datetime | None = None) -> OrderEvent:
    from_status = order.status
    if not can_transition(from_status, to_status):
        raise InvalidTransition(f"order {order.order_no}: {from_status} -> {to_status} not allowed")
    at = at or datetime.now(UTC)
    order.status = to_status
    order.updated_at = at
    event = OrderEvent(from_status=from_status, to_status=to_status, actor=actor, at=at)
    order.events.append(event)
    return event


def start_order(*, business_id: int, customer_id: int, order_no: int, quote: Quote,
                actor: Actor, at: datetime | None = None) -> Order:
    """Create a draft order from a priced quote, with its creation event."""
    at = at or datetime.now(UTC)
    order = Order(
        business_id=business_id,
        customer_id=customer_id,
        order_no=order_no,
        status=S.draft,
        total=quote.total,
        created_at=at,
        updated_at=at,
    )
    order.items = [
        OrderItem(catalog_item_id=line.item.id, quantity=line.quantity,
                  unit_price=line.unit_price, line_total=line.line_total)
        for line in quote.lines
    ]
    order.events.append(OrderEvent(from_status=None, to_status=S.draft, actor=actor, at=at))
    return order
