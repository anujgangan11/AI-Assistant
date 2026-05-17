from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import AssistantState
from src.graph.nodes import (
    context_loader,
    supervisor,
    research_expert,
    fundamental_analyst,
    memory_writer,
    responder,
)


def _route(state: AssistantState) -> str:
    return state.get("next", "research_expert")


def build_graph():
    g = StateGraph(AssistantState)

    g.add_node("context_loader", context_loader)
    g.add_node("supervisor", supervisor)
    g.add_node("research_expert", research_expert)
    g.add_node("fundamental_analyst", fundamental_analyst)
    g.add_node("memory_writer", memory_writer)
    g.add_node("responder", responder)

    g.set_entry_point("context_loader")
    g.add_edge("context_loader", "supervisor")

    g.add_conditional_edges(
        "supervisor",
        _route,
        {
            "fundamental_analyst": "fundamental_analyst",
            "research_expert": "research_expert",
        },
    )

    g.add_edge("fundamental_analyst", "memory_writer")
    g.add_edge("research_expert", "memory_writer")
    g.add_edge("memory_writer", "responder")
    g.add_edge("responder", END)

    return g.compile(checkpointer=MemorySaver())


graph = build_graph()
