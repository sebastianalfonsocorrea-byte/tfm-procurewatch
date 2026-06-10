from __future__ import annotations

from collections.abc import Callable

from .nodes import chunk_documents_node, require_evidence_node
from .state import Agent4State


def build_agent4_graph() -> Callable[[Agent4State], Agent4State]:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return _fallback_graph

    graph = StateGraph(Agent4State)
    graph.add_node("chunk_documents", chunk_documents_node)
    graph.add_node("require_evidence", require_evidence_node)
    graph.set_entry_point("chunk_documents")
    graph.add_edge("chunk_documents", "require_evidence")
    graph.add_edge("require_evidence", END)
    return graph.compile()


def _fallback_graph(state: Agent4State) -> Agent4State:
    return require_evidence_node(chunk_documents_node(state))
