from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from .schemas import DocumentChunk, DocumentRef, RetrievalResult


class Agent4State(TypedDict, total=False):
    run_id: str
    contract_key_canon: str
    source_record_id: str
    question: str
    corpus_index: Path
    output_path: Path
    chunk_size: int
    overlap: int
    retrieval_limit: int
    contract_context: dict[str, object]
    document_refs: list[DocumentRef]
    chunks: list[DocumentChunk]
    retrieved_context: list[RetrievalResult]
    answer: str
    citations: list[str]
    warnings: list[str]
    case_context: dict[str, object]
    agent2_score: dict[str, object]
    agent3_metrics: dict[str, object]
    embedding_client: Any
    embedding_fallback_client: Any
    active_embedding_client: Any
    vector_store: Any
    generation_client: Any
    embedding_metadata: dict[str, object]
    vector_upsert_report: dict[str, object]
    agent_output: dict[str, object]
