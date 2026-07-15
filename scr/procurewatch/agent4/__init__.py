from __future__ import annotations

from .boe_fetch import (
    BOE_HTML_SOURCE,
    DEFAULT_BOE_HTML_OUTPUT_DIR,
    build_boe_html_fetch_report,
    extract_boe_b_id,
    fetch_boe_html_document,
)
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
from .source_registry import (
    AGENT4_SCOPE,
    DEFAULT_AGENT4_SOURCE_REGISTRY_PATH,
    DOCUMENT_SOURCE_POLICY,
    IMPLEMENTED_IN_MVP,
    NOT_IMPLEMENTED_IN_MVP,
    build_agent4_capabilities,
    build_agent4_source_registry,
    build_agent4_source_registry_summary,
    write_agent4_source_registry,
)
from .state import Agent4State

__all__ = [
    "Agent4State",
    "Agent4IndexReport",
    "AGENT4_SCOPE",
    "AGENT4_EVALUATION_SCHEMA_VERSION",
    "DEFAULT_AGENT2_CANONICAL_PATH",
    "DEFAULT_AGENT4_EVAL_SET_PATH",
    "DEFAULT_AGENT4_EVALUATION_REPORT_PATH",
    "DEFAULT_AGENT4_SOURCE_REGISTRY_PATH",
    "DEFAULT_AGENT3_FEATURES_PATH",
    "DEFAULT_BOE_HTML_OUTPUT_DIR",
    "DEFAULT_CASE_CONTEXT_OUTPUT_PATH",
    "Agent4EvalCase",
    "BOE_HTML_SOURCE",
    "DeterministicEmbeddingClient",
    "DocumentChunk",
    "DocumentRef",
    "DOCUMENT_SOURCE_POLICY",
    "EmbeddingBatch",
    "EmbeddingMetadata",
    "GenerationResult",
    "IMPLEMENTED_IN_MVP",
    "NOT_IMPLEMENTED_IN_MVP",
    "OllamaEmbeddingClient",
    "OllamaGenerationClient",
    "QdrantSearchFilters",
    "QdrantVectorStore",
    "RetrievalResult",
    "build_agent4_capabilities",
    "build_agent4_graph",
    "build_agent4_evaluation_report",
    "build_agent4_source_registry",
    "build_agent4_source_registry_summary",
    "build_boe_html_fetch_report",
    "chunk_text",
    "evaluate_agent4_case_state",
    "extract_boe_b_id",
    "fetch_boe_html_document",
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
    "write_agent4_source_registry",
    "write_documents_manifest",
]
