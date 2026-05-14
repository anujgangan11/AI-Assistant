import hashlib
import hmac
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response

from src.config import settings
from src.db.connection import get_pool

router = APIRouter()
logger = logging.getLogger(__name__)

META_GRAPH_URL = "https://graph.facebook.com/v19.0"


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_signature(payload: bytes, header: str) -> bool:
    """Return True if X-Hub-Signature-256 matches HMAC-SHA256 of payload."""
    expected = hmac.new(
        settings.META_APP_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", header)


# ---------------------------------------------------------------------------
# Webhook verification (GET) — Meta calls this once when you register the URL
# ---------------------------------------------------------------------------

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> Response:
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        logger.info("Webhook verified by Meta")
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Forbidden")


# ---------------------------------------------------------------------------
# Inbound message handler (POST)
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def receive_message(request: Request) -> dict[str, str]:
    signature = request.headers.get("X-Hub-Signature-256", "")
    payload = await request.body()

    if not _verify_signature(payload, signature):
        logger.warning("Invalid webhook signature — request rejected")
        raise HTTPException(status_code=401, detail="Invalid signature")

    data: dict[str, Any] = await request.json()

    # WhatsApp Cloud API payload shape:
    # { "entry": [{ "changes": [{ "value": { "messages": [...] } }] }] }
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                await _handle_message(msg)

    # Meta expects a 200 quickly — always ack
    return {"status": "ok"}


async def _handle_message(msg: dict[str, Any]) -> None:
    phone: str = msg.get("from", "")
    msg_type: str = msg.get("type", "")
    wa_message_id: str = msg.get("id", "")

    if phone not in settings.allowed_set:
        logger.info("Ignored message from non-allowlisted number: %s", phone)
        return

    if msg_type != "text":
        logger.info("Ignored non-text message (type=%s) from %s", msg_type, phone)
        return

    text: str = msg.get("text", {}).get("body", "").strip()
    if not text:
        return

    logger.info("Queuing message from %s: %r", phone, text[:80])
    await _enqueue(phone, wa_message_id, text)


async def _enqueue(phone: str, wa_message_id: str, text: str) -> None:
    user_id = settings.phone_to_user_id.get(phone, phone)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO inbound_messages (wa_message_id, phone_number, user_id, message_text)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (wa_message_id) DO NOTHING
            """,
            wa_message_id,
            phone,
            user_id,
            text,
        )


# ---------------------------------------------------------------------------
# Outbound — send a reply via Meta REST API
# ---------------------------------------------------------------------------

async def send_whatsapp_message(to: str, text: str) -> None:
    """Send text to a WhatsApp number, splitting at 4096 chars if needed."""
    url = f"{META_GRAPH_URL}/{settings.META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    chunks = [text[i : i + 4096] for i in range(0, len(text), 4096)]

    async with httpx.AsyncClient(timeout=10) as client:
        for chunk in chunks:
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": chunk},
            }
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            logger.debug("Sent chunk (%d chars) to %s", len(chunk), to)
