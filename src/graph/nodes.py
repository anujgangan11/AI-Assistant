# TODO (slice 2): Implement all graph nodes

from src.graph.state import AssistantState


async def context_loader(state: AssistantState) -> dict:
    """Pull last 10 messages from the checkpointer and inject into state."""
    # The checkpointer handles history automatically via thread_id.
    # This node is a hook for any extra context fetching (e.g. user profile).
    return {}


async def supervisor(state: AssistantState) -> dict:
    """Route to the appropriate expert. v0: always routes to research_expert."""
    # In slice 3 we'll classify intent and fan out to multiple experts.
    return {}


async def research_expert(state: AssistantState) -> dict:
    """Web search + code execution expert backed by claude-sonnet-4-5."""
    # Will use tools/search.py and LangChain tool calling.
    return {"reply_text": "research_expert stub"}


async def memory_writer(state: AssistantState) -> dict:
    """Persist the turn to a JSON log. Real DB writes come in slice 3."""
    import json, pathlib, datetime

    log_path = pathlib.Path("memory_log.json")
    entry = {
        "ts": datetime.datetime.utcnow().isoformat(),
        "thread_id": state["thread_id"],
        "user_id": state["user_id"],
        "inbound": state["inbound_text"],
        "reply": state.get("reply_text", ""),
    }
    with log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return {}


async def responder(state: AssistantState) -> dict:
    """Format the reply and send it via the WhatsApp gateway."""
    from src.gateway.whatsapp import send_whatsapp_message

    reply = state.get("reply_text", "")
    if reply:
        await send_whatsapp_message(state["phone_number"], reply)
    return {}
