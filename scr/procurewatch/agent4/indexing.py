from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .chunking import chunk_text
from .corpus import DEFAULT_SYNTHETIC_CORPUS_INDEX, load_corpus_documents
from .embeddings import DEFAULT_OLLAMA_BASE_URL, OllamaEmbeddingClient
from .qdrant_store import (
    DEFAULT_QDRANT_COLLECTION,
    DEFAULT_QDRANT_URL,
    QdrantSearchFilters,
    QdrantVectorStore,
)
from .schemas import RetrievalResult


@dataclass(frozen=True, slots=True)
class Agent4IndexReport:
    collection_name: str
    documents_count: int
    chunks_count: int
    points_count: int
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    results: list[RetrievalResult]


def index_corpus_to_qdrant(
    *,
    corpus_index: Path = DEFAULT_SYNTHETIC_CORPUS_INDEX,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    collection_name: str = DEFAULT_QDRANT_COLLECTION,
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL,
    embedding_model: str,
    chunk_size: int = 900,
    overlap: int = 120,
    query: str | None = None,
    limit: int = 5,
    filters: QdrantSearchFilters | None = None,
) -> Agent4IndexReport:
    documents = load_corpus_documents(corpus_index)
    chunks = []
    for document in documents:
        chunks.extend(chunk_text(document, chunk_size=chunk_size, overlap=overlap))

    embedder = OllamaEmbeddingClient(base_url=ollama_base_url, model=embedding_model)
    embeddings = embedder.embed_texts([chunk.text for chunk in chunks])
    store = QdrantVectorStore(url=qdrant_url, collection_name=collection_name)
    upsert_report = store.upsert_chunks(chunks, embeddings.vectors, embeddings.metadata)

    results: list[RetrievalResult] = []
    if query:
        query_embedding = embedder.embed_query(query)
        query_vector = query_embedding.vectors[0] if query_embedding.vectors else []
        results = store.search(
            query_vector,
            limit=limit,
            filters=filters,
        )

    return Agent4IndexReport(
        collection_name=upsert_report.collection_name,
        documents_count=len(documents),
        chunks_count=len(chunks),
        points_count=upsert_report.points_count,
        embedding_provider=embeddings.metadata.provider,
        embedding_model=embeddings.metadata.model,
        embedding_dimension=embeddings.metadata.dimension,
        results=results,
    )
