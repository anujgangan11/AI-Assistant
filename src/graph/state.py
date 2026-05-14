# TODO (slice 2): Define the LangGraph state schema

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AssistantState(TypedDict):
    # Conversation thread id and user info
    thread_id: str
    user_id: str
    phone_number: str

    # The accumulated message list (LangGraph manages append-only via add_messages)
    messages: Annotated[list, add_messages]

    # Current inbound text (raw, post-debounce coalesce)
    inbound_text: str

    # Output produced by the responder node
    reply_text: str
