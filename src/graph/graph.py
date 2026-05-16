from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import AssistantState
from src.graph.nodes import (
    context_loader,
    research_expert,
    memory_writer,
    responder,
)


def build_graph():
    g = StateGraph(AssistantState)

    g.add_node("context_loader", context_loader)
    g.add_node("research_expert", research_expert)
    g.add_node("memory_writer", memory_writer)
    g.add_node("responder", responder)

    g.set_entry_point("context_loader")
    g.add_edge("context_loader", "research_expert")
    g.add_edge("research_expert", "memory_writer")
    g.add_edge("memory_writer", "responder")
    g.add_edge("responder", END)

    # MemorySaver keeps recent thread state in-process.
    # Switch to AsyncPostgresSaver in slice 3 for persistence across restarts.
    return g.compile(checkpointer=MemorySaver())


graph = build_graph()
