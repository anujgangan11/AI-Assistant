# TODO (slice 1): Implement the worker loop
#
# Responsibilities:
#   1. LISTEN on the 'inbound_message' Postgres channel
#   2. On NOTIFY (or on startup), claim a batch with FOR UPDATE SKIP LOCKED
#   3. Apply 8-second debounce per phone: collect burst messages, coalesce text
#   4. Resolve phone → user_id and build thread_id for the LangGraph checkpointer
#   5. Run the compiled LangGraph graph
#   6. Mark message done (or failed + increment retry_count)
#
# Sketch:
#
# async def run_worker():
#     pool = await get_pool()
#     async with pool.acquire() as listen_conn:
#         await listen_conn.add_listener("inbound_message", on_notify)
#         while True:
#             await asyncio.sleep(1)   # keep connection alive
#
# async def claim_and_process():
#     async with pool.acquire() as conn:
#         async with conn.transaction():
#             rows = await conn.fetch("""
#                 SELECT * FROM inbound_messages
#                 WHERE status = 'pending'
#                 ORDER BY received_at
#                 FOR UPDATE SKIP LOCKED
#                 LIMIT 10
#             """)
#             for row in rows:
#                 await conn.execute(
#                     "UPDATE inbound_messages SET status='claimed', claimed_at=NOW() WHERE id=$1",
#                     row["id"],
#                 )
#     # debounce + graph run happens outside the transaction

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_worker() -> None:  # pragma: no cover
    logger.info("Worker stub — not yet implemented")
    await asyncio.sleep(0)
