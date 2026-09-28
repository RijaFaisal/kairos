from enum import StrEnum


class OrderStatus(StrEnum):
    draft = "draft"
    awaiting_confirmation = "awaiting_confirmation"
    confirmed = "confirmed"
    preparing = "preparing"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"


class PaymentStatus(StrEnum):
    unpaid = "unpaid"
    paid = "paid"


class PaymentMethod(StrEnum):
    cash = "cash"
    online = "online"


class Actor(StrEnum):
    bot = "bot"
    owner = "owner"
    customer = "customer"


class Direction(StrEnum):
    inbound = "inbound"
    outbound = "outbound"
