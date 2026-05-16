import logging
from typing import Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def send_whatsapp_message(
    to: str, text: str, reply_jid: Optional[str] = None
) -> None:
    """Send text via the Baileys sidecar, chunking at 4096 chars if needed."""
    chunks = [text[i : i + 4096] for i in range(0, len(text), 4096)]
    async with httpx.AsyncClient(timeout=10) as client:
        for chunk in chunks:
            payload: dict = {"to": to, "text": chunk}
            if reply_jid:
                payload["reply_jid"] = reply_jid
            resp = await client.post(f"{settings.SIDECAR_URL}/send", json=payload)
            resp.raise_for_status()
            logger.debug("Sent chunk (%d chars) to %s", len(chunk), to)
