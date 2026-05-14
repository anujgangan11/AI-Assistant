# TODO (slice 2): Wire up the compiled LangGraph graph

from langgraph.graph import StateGraph, END
from src.graph.state import AssistantState
from src.graph.nodes import (
    context_loader,
    supervisor,
    research_expert,
    memory_writer,
    responder,
)


def build_graph():
    g = StateGraph(AssistantState)

    g.add_node("context_loader", context_loader)
    g.add_node("supervisor", supervisor)
    g.add_node("research_expert", research_expert)
    g.add_node("memory_writer", memory_writer)
    g.add_node("responder", responder)

    g.set_entry_point("context_loader")
    g.add_edge("context_loader", "supervisor")
    g.add_edge("supervisor", "research_expert")   # v0: always research
    g.add_edge("research_expert", "memory_writer")
    g.add_edge("memory_writer", "responder")
    g.add_edge("responder", END)

    # Checkpointer wired in by the worker (needs async DB connection)
    return g.compile()


# Module-level compiled graph (checkpointer added by worker at runtime)
graph = build_graph()
