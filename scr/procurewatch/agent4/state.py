from __future__ import annotations

from typing import TypedDict

from .schemas import DocumentChunk, DocumentRef, RetrievalResult


class Agent4State(TypedDict, total=False):
    run_id: str
    contract_key_canon: str
    source_record_id: str
    question: str
    contract_context: dict[str, object]
    document_refs: list[DocumentRef]
    chunks: list[DocumentChunk]
    retrieved_context: list[RetrievalResult]
    answer: str
    citations: list[str]
    warnings: list[str]
