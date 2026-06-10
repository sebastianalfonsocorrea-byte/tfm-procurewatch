from __future__ import annotations

from .chunking import chunk_text
from .state import Agent4State


def chunk_documents_node(state: Agent4State) -> Agent4State:
    chunks = []
    for document in state.get("document_refs", []):
        chunks.extend(chunk_text(document))
    return {**state, "chunks": chunks}


def require_evidence_node(state: Agent4State) -> Agent4State:
    if state.get("retrieved_context"):
        return state
    warnings = list(state.get("warnings", []))
    warnings.append("No hay evidencia documental recuperada para responder con trazabilidad.")
    return {**state, "warnings": warnings}
