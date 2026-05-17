from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AssistantState(TypedDict):
    thread_id: str
    user_id: str
    phone_number: str
    reply_jid: str  # original WhatsApp JID for routing the reply back correctly

    # Accumulated message list (LangGraph append-only via add_messages)
    messages: Annotated[list, add_messages]

    # Raw inbound text after debounce coalesce
    inbound_text: str

    # Mem0 semantic search results injected by context_loader
    memories_context: str

    # Final reply produced by research_expert / fundamental_analyst
    reply_text: str

    # Supervisor routing: "fundamental_analyst" | "research_expert"
    next: str

    # Extracted stock ticker (empty string if not a stock query)
    ticker: str
