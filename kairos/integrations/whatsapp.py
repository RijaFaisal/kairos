"""WhatsApp Cloud API client (ARCHITECTURE.md section 5.6). Phase 1: text only."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

GRAPH_URL = "https://graph.facebook.com/v21.0"
SESSION_WINDOW = timedelta(hours=24)


class OutsideSessionWindow(RuntimeError):
    """Free-form text is only allowed within 24h of the customer's last message."""


class WhatsAppError(RuntimeError):
    pass


def within_window(last_inbound_at: datetime | None, now: datetime | None = None) -> bool:
    if last_inbound_at is None:
        return False
    return (now or datetime.now(UTC)) - last_inbound_at < SESSION_WINDOW


class WhatsAppClient:
    def __init__(self, access_token: str, http: httpx.AsyncClient | None = None):
        if not access_token:
            raise RuntimeError("WA_ACCESS_TOKEN is not set")
        self._http = http or httpx.AsyncClient(
            timeout=15.0, headers={"Authorization": f"Bearer {access_token}"}
        )

    async def send_text(self, *, phone_number_id: str, to: str, body: str,
                        last_inbound_at: datetime | None) -> tuple[str, dict[str, Any]]:
        """Send a text message. Returns (wa_message_id, raw response)."""
        if not within_window(last_inbound_at):
            raise OutsideSessionWindow(f"last inbound message from {to} is older than 24h")
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        }
        resp = await self._http.post(f"{GRAPH_URL}/{phone_number_id}/messages", json=payload)
        if resp.status_code >= 400:
            raise WhatsAppError(f"send failed ({resp.status_code}): {resp.text}")
        data = resp.json()
        return data["messages"][0]["id"], data

    async def close(self) -> None:
        await self._http.aclose()
