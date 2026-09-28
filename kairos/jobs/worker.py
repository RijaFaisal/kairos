"""arq worker: process one inbound message (Phase 1).

load context -> one LLM extraction -> decide in code -> create draft order ->
templated reply. From Phase 2 this becomes the LangGraph customer graph.

Idempotency: the inbound message row is locked and marked processed in the same
transaction that creates the order, so a retried job never creates a second
order. The WhatsApp send happens after commit, so a reply is sent at most once.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from arq.connections import RedisSettings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agent.decide import (
    Ambiguous,
    AskQuantity,
    CreateOrder,
    Decision,
    NotFound,
    Reply,
    Unavailable,
    decide,
)
from kairos.agent.replies import Replies
from kairos.config import get_settings
from kairos.db import models
from kairos.db.session import get_sessionmaker
from kairos.domain.business import BusinessSettings
from kairos.domain.catalog import CatalogItem
from kairos.domain.enums import Actor, Direction, PaymentMethod
from kairos.domain.orders import start_order
from kairos.integrations.llm import ExtractionFailed, LLMClient
from kairos.integrations.whatsapp import OutsideSessionWindow, WhatsAppClient, WhatsAppError

log = logging.getLogger(__name__)


async def process_message(ctx: dict[str, Any], message_id: int) -> None:
    llm: LLMClient = ctx["llm"]
    wa: WhatsAppClient = ctx["wa"]

    async with get_sessionmaker()() as session:
        msg = await session.get(models.Message, message_id, with_for_update=True)
        if msg is None or msg.processed_at is not None or msg.direction != Direction.inbound:
            return
        conversation = await session.get(models.Conversation, msg.conversation_id)
        customer = await session.get(models.Customer, conversation.customer_id)
        business = await session.get(models.Business, msg.business_id)
        now = datetime.now(UTC)

        owners = set(business.owner_phones) | set(get_settings().owner_phone_list)
        if customer.phone in owners or conversation.bot_paused:
            # Owner commands and handoff arrive in Phase 2; store only.
            msg.processed_at = now
            await session.commit()
            return

        settings = BusinessSettings.model_validate(business.settings)
        catalog = await load_catalog(session, business.id)

        if msg.body is None:
            text = Replies(business.name, settings, None).text_only()
        else:
            try:
                extraction = await llm.extract(msg.body, catalog)
            except ExtractionFailed:
                text = Replies(business.name, settings, None).not_understood()
            else:
                replies = Replies(business.name, settings, extraction.language)
                text = await apply_decision(session, decide(extraction, catalog), replies,
                                            business, customer, catalog, now)

        outbound = models.Message(business_id=business.id, conversation_id=conversation.id,
                                  direction=Direction.outbound, body=text)
        session.add(outbound)
        msg.processed_at = now
        await session.commit()

        try:
            wa_message_id, raw = await wa.send_text(
                phone_number_id=business.wa_phone_number_id, to=customer.phone, body=text,
                last_inbound_at=conversation.last_inbound_at,
            )
        except (OutsideSessionWindow, WhatsAppError, httpx.HTTPError):
            log.exception("reply to message %s not sent", message_id)
            return
        outbound.wa_message_id = wa_message_id
        outbound.raw = raw
        await session.commit()


async def apply_decision(session: AsyncSession, decision: Decision, replies: Replies,
                         business: models.Business, customer: models.Customer,
                         catalog: list[CatalogItem], now: datetime) -> str:
    match decision:
        case CreateOrder():
            order_no = await next_order_no(session, business.id)
            order = start_order(business_id=business.id, customer_id=customer.id,
                                order_no=order_no, quote=decision.quote, actor=Actor.bot, at=now)
            order.delivery_address = decision.delivery_address
            order.payment_method = PaymentMethod(decision.payment_method) if decision.payment_method else None
            if decision.delivery_time:
                # Parsed into delivery_at once delivery rules land (Phase 2).
                order.notes = f"Requested delivery time: {decision.delivery_time}"
            session.add(order)
            return replies.order_summary(order_no, decision.quote)
        case AskQuantity():
            return replies.ask_quantity(decision.names)
        case NotFound():
            return replies.not_found(decision.mentions)
        case Ambiguous():
            return replies.ambiguous(decision.mention, decision.options)
        case Unavailable():
            return replies.unavailable(decision.names)
        case Reply(kind="greeting"):
            return replies.greeting()
        case Reply(kind="catalog"):
            return replies.catalog(catalog)
        case Reply(kind="received"):
            return replies.received()
        case _:
            return replies.not_understood()


async def load_catalog(session: AsyncSession, business_id: int) -> list[CatalogItem]:
    rows = await session.scalars(
        select(models.CatalogItem).where(models.CatalogItem.business_id == business_id)
        .order_by(models.CatalogItem.id)
    )
    return [
        CatalogItem(id=r.id, name=r.name, price=r.price, unit=r.unit, aliases=tuple(r.aliases),
                    available=r.available, category=r.category)
        for r in rows
    ]


async def next_order_no(session: AsyncSession, business_id: int) -> int:
    # Lock the business row so two workers can't hand out the same number.
    await session.execute(
        select(models.Business.id).where(models.Business.id == business_id).with_for_update()
    )
    current = await session.scalar(
        select(func.coalesce(func.max(models.Order.order_no), 0))
        .where(models.Order.business_id == business_id)
    )
    return current + 1


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["llm"] = LLMClient(settings)
    ctx["wa"] = WhatsAppClient(settings.wa_access_token)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["llm"].close()
    await ctx["wa"].close()


def _redis_settings() -> RedisSettings:
    url = get_settings().redis_url
    if not url:
        raise RuntimeError("REDIS_URL is not set")
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    functions = [process_message]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
    max_tries = 3
    job_timeout = 120
