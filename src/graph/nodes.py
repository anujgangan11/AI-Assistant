import asyncio
import json
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


_SUPERVISOR_PROMPT = """\
You are a query router for a personal AI assistant with a financial specialist.

Classify the user's message into one of these intents:
- "fundamental_analyst": questions about a company's financials, earnings, revenue, P/E ratio,
  analyst ratings, business fundamentals, or recent news about a specific stock/company.
- "research_expert": everything else — general questions, personal topics, reminders, coding help, etc.

If the intent is "fundamental_analyst", extract the primary stock ticker symbol (e.g. AAPL, NVDA).
If no ticker is mentioned, infer it from the company name. If you cannot determine a ticker, use "".

Respond with ONLY valid JSON, no markdown, no explanation:
{"intent": "<intent>", "ticker": "<TICKER or empty string>"}
"""


async def supervisor(state: AssistantState) -> dict:
    llm = _get_llm()
    try:
        response = await llm.ainvoke([
            SystemMessage(content=_SUPERVISOR_PROMPT),
            HumanMessage(content=state["inbound_text"]),
        ])
        raw = response.content.strip()
        # Strip markdown fences if LLM wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        intent = parsed.get("intent", "research_expert")
        ticker = parsed.get("ticker", "").upper().strip()
        if intent not in ("fundamental_analyst", "research_expert"):
            intent = "research_expert"
    except Exception:
        logger.exception("Supervisor classification failed — defaulting to research_expert")
        intent = "research_expert"
        ticker = ""

    logger.info("Supervisor → intent=%s ticker=%s", intent, ticker)
    return {"next": intent, "ticker": ticker}


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


async def fundamental_analyst(state: AssistantState) -> dict:
    from src.tools.robinhood import fetch_stock_data

    ticker = state.get("ticker", "").strip()
    if not ticker:
        return await research_expert(state)

    llm = _get_llm()
    memories = state.get("memories_context", "")

    data = await fetch_stock_data(ticker)

    system = (
        "You are a fundamental investment analyst. "
        "Analyse the data below and give a clear, structured assessment. "
        "Cover: business quality, valuation, key risks, and whether it looks attractive. "
        "Be direct — the user wants actionable insight, not a disclaimer parade."
    )
    if memories:
        system += f"\n\nUser context:\n{memories}"

    user_content = (
        f"User asked: {state['inbound_text']}\n\n"
        f"=== FUNDAMENTALS ({ticker}) ===\n{data.get('get_fundamentals', 'N/A')}\n\n"
        f"=== ANALYST RATINGS ===\n{data.get('get_ratings', 'N/A')}\n\n"
        f"=== RECENT EARNINGS ===\n{data.get('get_earnings', 'N/A')}\n\n"
        f"=== NEWS ===\n{data.get('get_news', 'No recent news.')}"
    )

    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user_content),
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
