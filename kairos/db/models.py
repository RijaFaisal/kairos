"""Postgres schema (ARCHITECTURE.md section 6).

Money is integer units of the business's currency. Times are timestamptz (UTC).
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from kairos.domain.enums import Actor, Direction, OrderStatus, PaymentMethod, PaymentStatus


class Base(DeclarativeBase):
    pass


def _enum(cls: type[StrEnum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    wa_phone_number_id: Mapped[str] = mapped_column(Text, unique=True)
    owner_phones: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    timezone: Mapped[str] = mapped_column(Text, server_default="Asia/Karachi")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("business_id", "phone"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    phone: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    default_address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("business_id", "name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    price: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(Text)
    available: Mapped[bool] = mapped_column(Boolean, server_default="true")
    category: Mapped[str | None] = mapped_column(Text)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("business_id", "order_no"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[OrderStatus] = mapped_column(_enum(OrderStatus, "order_status"))
    payment_status: Mapped[PaymentStatus] = mapped_column(
        _enum(PaymentStatus, "payment_status"), default=PaymentStatus.unpaid,
        server_default=PaymentStatus.unpaid.value,
    )
    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        _enum(PaymentMethod, "payment_method")
    )
    delivery_address: Mapped[str | None] = mapped_column(Text)
    delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    events: Mapped[list["OrderEvent"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    catalog_item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    # NULL from_status marks the event that created the order.
    from_status: Mapped[OrderStatus | None] = mapped_column(_enum(OrderStatus, "order_status"))
    to_status: Mapped[OrderStatus] = mapped_column(_enum(OrderStatus, "order_status"))
    actor: Mapped[Actor] = mapped_column(_enum(Actor, "event_actor"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="events")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("business_id", "customer_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    bot_paused: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    # Unique so Meta's webhook retries are stored once. NULL for an outbound
    # message whose send failed.
    wa_message_id: Mapped[str | None] = mapped_column(Text, unique=True)
    direction: Mapped[Direction] = mapped_column(_enum(Direction, "message_direction"))
    body: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set once the worker has handled an inbound message, so a retried job does
    # not create a second order.
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
