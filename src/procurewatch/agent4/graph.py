from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from procurewatch.settings import Settings

from .corpus import DEFAULT_SYNTHETIC_CORPUS_INDEX
from .embeddings import DeterministicEmbeddingClient, OllamaEmbeddingClient
from .generation import OllamaGenerationClient
from .nodes import (
    chunk_documents_node,
    discover_documents_node,
    embed_and_upsert_node,
    extract_text_node,
    generate_case_context_node,
    load_contract_context_node,
    persist_agent_output_node,
    retrieve_context_node,
)
from .qdrant_store import DEFAULT_QDRANT_COLLECTION, DEFAULT_QDRANT_URL, QdrantVectorStore
from .state import Agent4State

_NODE_SEQUENCE: tuple[tuple[str, Callable[[Agent4State], Agent4State]], ...] = (
    ("load_contract_context", load_contract_context_node),
    ("discover_documents", discover_documents_node),
    ("extract_text", extract_text_node),
    ("chunk_text", chunk_documents_node),
    ("embed_and_upsert", embed_and_upsert_node),
    ("retrieve_context", retrieve_context_node),
    ("generate_case_context", generate_case_context_node),
    ("persist_agent_output", persist_agent_output_node),
)


def build_agent4_graph() -> Callable[[Agent4State], Agent4State]:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return _fallback_graph

    graph = StateGraph(Agent4State)
    for node_name, node_func in _NODE_SEQUENCE:
        graph.add_node(node_name, node_func)
    graph.set_entry_point(_NODE_SEQUENCE[0][0])
    for current_node, next_node in zip(_NODE_SEQUENCE, _NODE_SEQUENCE[1:], strict=False):
        graph.add_edge(current_node[0], next_node[0])
    graph.add_edge(_NODE_SEQUENCE[-1][0], END)
    return graph.compile()


def run_agent4_graph(state: Agent4State) -> Agent4State:
    graph = build_agent4_graph()
    if hasattr(graph, "invoke"):
        return graph.invoke(state)
    return graph(state)


def run_agent4_case_flow(
    *,
    contract_key_canon: str,
    question: str,
    corpus_index: Path = DEFAULT_SYNTHETIC_CORPUS_INDEX,
    output_path: Path | None = None,
    contract_context: dict[str, object] | None = None,
    agent2_score: dict[str, object] | None = None,
    agent3_metrics: dict[str, object] | None = None,
    warnings: list[str] | None = None,
    use_services: bool = False,
    qdrant_url: str | None = None,
    collection_name: str = DEFAULT_QDRANT_COLLECTION,
    ollama_base_url: str | None = None,
    embedding_model: str | None = None,
    llm_model: str | None = None,
    chunk_size: int = 900,
    overlap: int = 120,
    retrieval_limit: int = 5,
) -> Agent4State:
    settings = Settings.from_env()
    state: Agent4State = {
        "run_id": str(uuid4()),
        "contract_key_canon": contract_key_canon,
        "question": question,
        "corpus_index": corpus_index,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "retrieval_limit": retrieval_limit,
    }
    if contract_context is not None:
        state["contract_context"] = contract_context
    if agent2_score is not None:
        state["agent2_score"] = agent2_score
    if agent3_metrics is not None:
        state["agent3_metrics"] = agent3_metrics
    if warnings:
        state["warnings"] = list(warnings)
    if use_services:
        resolved_ollama_base_url = (
            ollama_base_url or settings.ollama_base_url or "http://localhost:11434"
        )
        state["embedding_client"] = OllamaEmbeddingClient(
            base_url=resolved_ollama_base_url,
            model=embedding_model or settings.ollama_embedding_model,
        )
        state["embedding_fallback_client"] = DeterministicEmbeddingClient()
        state["vector_store"] = QdrantVectorStore(
            url=qdrant_url or settings.qdrant_url or DEFAULT_QDRANT_URL,
            collection_name=collection_name,
        )
        state["generation_client"] = OllamaGenerationClient(
            base_url=resolved_ollama_base_url,
            model=llm_model or settings.ollama_model,
        )
    if output_path is not None:
        state["output_path"] = output_path
    return run_agent4_graph(state)


def _fallback_graph(state: Agent4State) -> Agent4State:
    current_state = state
    for _node_name, node_func in _NODE_SEQUENCE:
        current_state = node_func(current_state)
    return current_state
