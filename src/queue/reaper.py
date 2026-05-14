# TODO (slice 1): Implement the reaper cron
#
# Runs every 60 seconds. Resets 'claimed' messages that have been stuck
# for more than 2 minutes back to 'pending' so another worker can retry them.
#
# async def reap_stuck_messages():
#     pool = await get_pool()
#     async with pool.acquire() as conn:
#         updated = await conn.fetchval("""
#             UPDATE inbound_messages
#             SET status = 'pending',
#                 claimed_at = NULL,
#                 worker_id  = NULL,
#                 retry_count = retry_count + 1
#             WHERE status = 'claimed'
#               AND claimed_at < NOW() - INTERVAL '2 minutes'
#             RETURNING id
#         """)
#         if updated:
#             logger.info("Reaper reset %d stuck message(s)", len(updated))

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_reaper() -> None:  # pragma: no cover
    logger.info("Reaper stub — not yet implemented")
    await asyncio.sleep(0)
