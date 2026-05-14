"""
Simulate an inbound WhatsApp message by inserting directly into the queue.
Use this to test the worker without needing the sidecar running.

Usage:
  python scripts/test_webhook.py "hello from test"
"""
import asyncio
import sys
import pathlib
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.db.connection import get_pool, close_pool
from src.config import settings


async def main() -> None:
    text = " ".join(sys.argv[1:]) or "Hello from test script!"
    phone = settings.ALLOWED_PHONE_NUMBERS[0]
    wa_message_id = f"test_{uuid.uuid4().hex[:8]}"

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
            phone,
            text,
        )

    print(f"Inserted: [{wa_message_id}] from {phone}: {text!r}")
    print("Check queue:")
    print("  psql assistant -c \"SELECT id, message_text, status FROM inbound_messages ORDER BY received_at DESC LIMIT 5;\"")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
