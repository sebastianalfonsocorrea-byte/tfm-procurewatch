from __future__ import annotations

from .chunking import chunk_text
from .corpus import load_corpus_documents, write_documents_manifest
from .document_loader import (
    load_document,
    load_html_document,
    load_markdown_document,
    load_text_document,
)
from .embeddings import (
    DeterministicEmbeddingClient,
    EmbeddingBatch,
    EmbeddingMetadata,
    OllamaEmbeddingClient,
)
from .evaluation import (
    AGENT4_EVALUATION_SCHEMA_VERSION,
    DEFAULT_AGENT4_EVAL_SET_PATH,
    DEFAULT_AGENT4_EVALUATION_REPORT_PATH,
    Agent4EvalCase,
    build_agent4_evaluation_report,
    evaluate_agent4_case_state,
    load_agent4_eval_cases,
    run_agent4_evaluation,
)
from .generation import GenerationResult, OllamaGenerationClient
from .graph import build_agent4_graph, run_agent4_case_flow, run_agent4_graph
from .indexing import Agent4IndexReport, index_corpus_to_qdrant
from .integration import (
    DEFAULT_AGENT2_CANONICAL_PATH,
    DEFAULT_AGENT3_FEATURES_PATH,
    DEFAULT_CASE_CONTEXT_OUTPUT_PATH,
    agent2_contract_from_record,
    load_agent3_metrics_for_contract,
    load_contract_context_from_canonical,
    run_agent4_case_context,
)
from .qdrant_store import QdrantSearchFilters, QdrantVectorStore
from .retrieval import keyword_retrieve
from .schemas import DocumentChunk, DocumentRef, RetrievalResult
from .state import Agent4State

__all__ = [
    "Agent4State",
    "Agent4IndexReport",
    "AGENT4_EVALUATION_SCHEMA_VERSION",
    "DEFAULT_AGENT2_CANONICAL_PATH",
    "DEFAULT_AGENT4_EVAL_SET_PATH",
    "DEFAULT_AGENT4_EVALUATION_REPORT_PATH",
    "DEFAULT_AGENT3_FEATURES_PATH",
    "DEFAULT_CASE_CONTEXT_OUTPUT_PATH",
    "Agent4EvalCase",
    "DeterministicEmbeddingClient",
    "DocumentChunk",
    "DocumentRef",
    "EmbeddingBatch",
    "EmbeddingMetadata",
    "GenerationResult",
    "OllamaEmbeddingClient",
    "OllamaGenerationClient",
    "QdrantSearchFilters",
    "QdrantVectorStore",
    "RetrievalResult",
    "build_agent4_graph",
    "build_agent4_evaluation_report",
    "chunk_text",
    "evaluate_agent4_case_state",
    "index_corpus_to_qdrant",
    "agent2_contract_from_record",
    "load_agent3_metrics_for_contract",
    "load_contract_context_from_canonical",
    "load_corpus_documents",
    "load_agent4_eval_cases",
    "load_document",
    "load_html_document",
    "load_markdown_document",
    "load_text_document",
    "keyword_retrieve",
    "run_agent4_case_flow",
    "run_agent4_case_context",
    "run_agent4_evaluation",
    "run_agent4_graph",
    "write_documents_manifest",
]
