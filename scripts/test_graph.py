"""End-to-end graph test — no WhatsApp needed. Skips the responder send."""
import asyncio
import logging
from unittest.mock import AsyncMock, patch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

from langchain_core.messages import HumanMessage
from src.graph.graph import graph


async def main():
    state = {
        "thread_id": "test_user",
        "user_id": "test_user",
        "phone_number": "+10000000000",
        "reply_jid": "test@lid",
        "inbound_text": "I love hiking. What are some good trails near San Francisco?",
        "messages": [HumanMessage(content="I love hiking. What are some good trails near San Francisco?")],
        "reply_text": "",
        "memories_context": "",
    }

    # Patch send so we don't need a running sidecar
    with patch("src.gateway.whatsapp.send_whatsapp_message", new_callable=AsyncMock):
        result = await graph.ainvoke(
            state, config={"configurable": {"thread_id": "test_user"}}
        )

    print("\n=== MEMORIES INJECTED ===")
    print(result["memories_context"] or "(none yet — first message)")

    print("\n=== AI REPLY ===")
    print(result["reply_text"])


asyncio.run(main())
