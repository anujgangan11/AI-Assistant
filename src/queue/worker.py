import asyncio
import logging
import uuid as uuid_mod

import asyncpg
import httpx

from src.config import settings
from src.db.connection import get_pool

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 8
WORKER_ID = str(uuid_mod.uuid4())[:8]

# phone → running debounce Task
_debounce_tasks: dict[str, asyncio.Task] = {}


# ─── Entry point ──────────────────────────────────────────────────────────────

async def run_worker() -> None:
    pool = await get_pool()
    logger.info("Worker %s starting", WORKER_ID)

    # Catch up on anything already pending before we connected
    await _drain_pending(pool)

    # Dedicated connection for LISTEN — must not be returned to pool
    listen_conn = await asyncpg.connect(dsn=settings.DATABASE_URL)

    def _on_notify(_conn, _pid, _channel, payload: str) -> None:
        asyncio.create_task(_on_new_message(payload, pool))

    await listen_conn.add_listener("inbound_message", _on_notify)
    logger.info("Worker %s listening on Postgres channel 'inbound_message'", WORKER_ID)

    # Run reaper concurrently
    reaper_task = asyncio.create_task(_run_reaper(pool))

    try:
        while True:
            await asyncio.sleep(60)
    finally:
        reaper_task.cancel()
        await listen_conn.remove_listener("inbound_message", _on_notify)
        await listen_conn.close()


# ─── NOTIFY handler ───────────────────────────────────────────────────────────

async def _on_new_message(message_id: str, pool: asyncpg.Pool) -> None:
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT phone_number FROM inbound_messages WHERE id = $1",
                uuid_mod.UUID(message_id),
            )
        if row:
            _schedule_debounce(row["phone_number"], pool)
    except Exception:
        logger.exception("Error handling notify for message %s", message_id)


# ─── Debounce ─────────────────────────────────────────────────────────────────

def _schedule_debounce(phone: str, pool: asyncpg.Pool) -> None:
    existing = _debounce_tasks.get(phone)
    if existing and not existing.done():
        existing.cancel()
    _debounce_tasks[phone] = asyncio.create_task(_debounce_then_process(phone, pool))


async def _debounce_then_process(phone: str, pool: asyncpg.Pool) -> None:
    try:
        await asyncio.sleep(DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return  # another message arrived — a new task was scheduled
    _debounce_tasks.pop(phone, None)
    await _process_phone(phone, pool)


# ─── Claim + process ──────────────────────────────────────────────────────────

async def _process_phone(phone: str, pool: asyncpg.Pool) -> None:
    # Claim all pending messages for this phone atomically
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                SELECT id, message_text, user_id
                FROM   inbound_messages
                WHERE  phone_number = $1
                  AND  status = 'pending'
                ORDER  BY received_at
                FOR UPDATE SKIP LOCKED
                """,
                phone,
            )
            if not rows:
                return

            ids = [r["id"] for r in rows]
            await conn.execute(
                """
                UPDATE inbound_messages
                SET    status = 'claimed', claimed_at = NOW(), worker_id = $1
                WHERE  id = ANY($2)
                """,
                WORKER_ID,
                ids,
            )

    combined_text = "\n".join(r["message_text"] for r in rows)
    user_id = rows[0]["user_id"]
    logger.info(
        "Processing %d message(s) from %s (user=%s): %r",
        len(rows), phone, user_id, combined_text[:80],
    )

    try:
        reply = await _generate_reply(combined_text)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.SIDECAR_URL}/send",
                json={"to": phone, "text": reply},
            )
            resp.raise_for_status()

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE inbound_messages SET status='done', done_at=NOW() WHERE id=ANY($1)",
                ids,
            )
        logger.info("Replied to %s, marked %d message(s) done", phone, len(ids))

    except Exception as exc:
        logger.exception("Failed to process messages from %s", phone)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE inbound_messages
                SET    status = 'failed',
                       retry_count = retry_count + 1,
                       last_error = $1
                WHERE  id = ANY($2)
                """,
                str(exc),
                ids,
            )


async def _generate_reply(text: str) -> str:
    # ── STUB: echo reply — replaced by LangGraph in step 2 ──────────────────
    return f"Echo: {text}"


# ─── Startup drain ────────────────────────────────────────────────────────────

async def _drain_pending(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT phone_number FROM inbound_messages WHERE status = 'pending'"
        )
    if rows:
        logger.info("Found %d phone(s) with pending messages on startup", len(rows))
        for row in rows:
            _schedule_debounce(row["phone_number"], pool)


# ─── Reaper ───────────────────────────────────────────────────────────────────

async def _run_reaper(pool: asyncpg.Pool) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            async with pool.acquire() as conn:
                ids = await conn.fetchval(
                    """
                    UPDATE inbound_messages
                    SET    status = 'pending',
                           claimed_at = NULL,
                           worker_id  = NULL,
                           retry_count = retry_count + 1
                    WHERE  status = 'claimed'
                      AND  claimed_at < NOW() - INTERVAL '2 minutes'
                    RETURNING id
                    """
                )
            if ids:
                logger.info("Reaper reset %s stuck message(s)", ids)
        except Exception:
            logger.exception("Reaper error")


# ─── Standalone entry ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    asyncio.run(run_worker())
