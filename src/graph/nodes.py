import asyncio
import logging
from typing import Optional

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from src.graph.state import AssistantState

logger = logging.getLogger(__name__)

_llm: Optional[ChatOllama] = None


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        from src.config import settings
        _llm = ChatOllama(
            model=settings.OLLAMA_LLM_MODEL,
            base_url=settings.OLLAMA_LLM_URL,
            num_ctx=4096,
        )
    return _llm


async def context_loader(state: AssistantState) -> dict:
    from src.graph.mem0_client import get_memory
    mem = get_memory()

    try:
        results = await asyncio.to_thread(
            mem.search,
            state["inbound_text"],
            filters={"user_id": state["user_id"]},
            top_k=5,
        )
        memories = results.get("results", []) if results else []
        memories_context = "\n".join(f"- {r['memory']}" for r in memories)
    except Exception:
        logger.exception("Mem0 search failed — proceeding without memories")
        memories_context = ""

    return {"memories_context": memories_context}


async def supervisor(state: AssistantState) -> dict:
    # v0: always routes to research_expert; intent classification comes in slice 3
    return {}


async def research_expert(state: AssistantState) -> dict:
    llm = _get_llm()

    system = "You are a helpful personal AI assistant. Reply naturally and concisely."
    memories = state.get("memories_context", "")
    if memories:
        system += f"\n\nWhat you know about the user:\n{memories}"

    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=state["inbound_text"]),
    ])

    return {
        "reply_text": response.content,
        "messages": [AIMessage(content=response.content)],
    }


async def memory_writer(state: AssistantState) -> dict:
    from src.graph.mem0_client import get_memory
    mem = get_memory()

    messages = [
        {"role": "user", "content": state["inbound_text"]},
        {"role": "assistant", "content": state.get("reply_text", "")},
    ]
    try:
        await asyncio.to_thread(mem.add, messages, user_id=state["user_id"], infer=True)
    except Exception:
        logger.exception("Mem0 add failed — memory not persisted for this turn")

    # LangGraph requires at least one state field to be returned
    return {"memories_context": state.get("memories_context", "")}


async def responder(state: AssistantState) -> dict:
    from src.gateway.whatsapp import send_whatsapp_message

    reply = state.get("reply_text", "")
    if reply:
        await send_whatsapp_message(
            state["phone_number"],
            reply,
            reply_jid=state.get("reply_jid"),
        )
    return {"reply_text": reply}
