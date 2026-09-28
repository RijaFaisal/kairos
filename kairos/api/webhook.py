"""WhatsApp webhook (ARCHITECTURE.md section 5.1).

GET  /webhook: Meta verification handshake.
POST /webhook: verify signature, store each message once (dedupe on
wa_message_id), enqueue processing, return 200 fast.
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.config import get_settings, normalize_phone
from kairos.db.models import Business, Conversation, Customer, Message
from kairos.db.session import get_sessionmaker
from kairos.domain.enums import Direction

log = logging.getLogger(__name__)
router = APIRouter()


@dataclass(frozen=True)
class InboundMessage:
    phone_number_id: str
    wa_message_id: str
    sender: str
    sender_name: str | None
    body: str | None
    sent_at: datetime
    raw: dict[str, Any]


def verify_signature(body: bytes, header: str | None, app_secret: str) -> bool:
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def parse_messages(payload: dict[str, Any]) -> list[InboundMessage]:
    """Pull customer messages out of a webhook payload. Status callbacks are logged and skipped."""
    out: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            for status in value.get("statuses", []):
                log.info("status callback: %s %s", status.get("id"), status.get("status"))
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                sender = normalize_phone(msg.get("from", ""))
                if not msg.get("id") or not sender:
                    continue
                body = msg.get("text", {}).get("body") if msg.get("type") == "text" else None
                out.append(InboundMessage(
                    phone_number_id=phone_number_id,
                    wa_message_id=msg["id"],
                    sender=sender,
                    sender_name=names.get(msg.get("from")),
                    body=body,
                    sent_at=datetime.fromtimestamp(int(msg.get("timestamp", 0)), UTC)
                    if msg.get("timestamp") else datetime.now(UTC),
                    raw=msg,
                ))
    return out


@router.get("/webhook")
async def verify(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
) -> Response:
    expected = get_settings().wa_verify_token
    if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403)


@router.post("/webhook")
async def receive(request: Request) -> dict[str, str]:
    body = await request.body()
    if not verify_signature(body, request.headers.get("X-Hub-Signature-256"),
                            get_settings().wa_app_secret):
        raise HTTPException(status_code=403)

    to_enqueue: list[int] = []
    async with get_sessionmaker()() as session:
        for inbound in parse_messages(await request.json()):
            message_id = await store_inbound(session, inbound)
            if message_id is not None:
                to_enqueue.append(message_id)
        await session.commit()

    # If Redis is down we return 500 so Meta retries; the retry finds the
    # stored-but-unprocessed message and enqueues it again.
    for message_id in to_enqueue:
        await request.app.state.arq.enqueue_job("process_message", message_id,
                                                _job_id=f"msg:{message_id}")
    return {"status": "ok"}


async def store_inbound(session: AsyncSession, inbound: InboundMessage) -> int | None:
    """Store one inbound message. Returns its id if it still needs processing."""
    business = await session.scalar(
        select(Business).where(Business.wa_phone_number_id == inbound.phone_number_id)
    )
    if business is None:
        log.warning("message for unknown phone_number_id %s", inbound.phone_number_id)
        return None

    customer_id = await session.scalar(
        insert(Customer)
        .values(business_id=business.id, phone=inbound.sender, name=inbound.sender_name)
        .on_conflict_do_update(
            index_elements=[Customer.business_id, Customer.phone],
            set_={"name": func.coalesce(Customer.name, inbound.sender_name)},
        )
        .returning(Customer.id)
    )
    conversation_id = await session.scalar(
        insert(Conversation)
        .values(business_id=business.id, customer_id=customer_id, last_inbound_at=inbound.sent_at)
        .on_conflict_do_update(
            index_elements=[Conversation.business_id, Conversation.customer_id],
            set_={"last_inbound_at": func.greatest(Conversation.last_inbound_at, inbound.sent_at)},
        )
        .returning(Conversation.id)
    )
    message_id = await session.scalar(
        insert(Message)
        .values(business_id=business.id, conversation_id=conversation_id,
                wa_message_id=inbound.wa_message_id, direction=Direction.inbound,
                body=inbound.body, raw=inbound.raw)
        .on_conflict_do_nothing(index_elements=[Message.wa_message_id])
        .returning(Message.id)
    )
    if message_id is not None:
        return message_id

    # Duplicate delivery from Meta. Re-enqueue only if it was never processed
    # (e.g. the first enqueue failed); arq's _job_id stops a double run.
    existing = await session.execute(
        select(Message.id, Message.processed_at).where(Message.wa_message_id == inbound.wa_message_id)
    )
    row = existing.one()
    return row.id if row.processed_at is None else None
