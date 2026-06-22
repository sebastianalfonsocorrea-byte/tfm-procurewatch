from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen
from uuid import NAMESPACE_URL, uuid5

from .embeddings import EmbeddingMetadata
from .schemas import DocumentChunk, RetrievalResult

DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_QDRANT_COLLECTION = "procurement_documents"


@dataclass(frozen=True, slots=True)
class QdrantStatus:
    url: str
    reachable: bool
    detail: str


def check_qdrant_health(url: str, *, timeout: float = 3.0) -> QdrantStatus:
    health_url = url.rstrip("/") + "/health"
    try:
        with urlopen(health_url, timeout=timeout) as response:
            detail = response.read().decode("utf-8", errors="replace").strip()
            return QdrantStatus(url=url, reachable=200 <= response.status < 300, detail=detail)
    except (OSError, URLError) as exc:
        return QdrantStatus(url=url, reachable=False, detail=str(exc))


@dataclass(frozen=True, slots=True)
class QdrantSearchFilters:
    contract_key_canon: str | None = None
    source: str | None = None
    document_type: str | None = None


@dataclass(frozen=True, slots=True)
class QdrantUpsertReport:
    collection_name: str
    points_count: int
    vector_size: int


class QdrantVectorStore:
    def __init__(
        self,
        *,
        url: str = DEFAULT_QDRANT_URL,
        collection_name: str = DEFAULT_QDRANT_COLLECTION,
        client: Any | None = None,
    ) -> None:
        self.url = url
        self.collection_name = collection_name
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise ImportError(
                "qdrant-client is required for QdrantVectorStore. "
                'Install it with: python -m pip install -e ".[rag]"'
            ) from exc
        self._client = QdrantClient(url=self.url)
        return self._client

    def ensure_collection(self, *, vector_size: int) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be greater than 0")
        client = self.client
        if _collection_exists(client, self.collection_name):
            return

        models = _qdrant_models()
        client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        embedding_metadata: EmbeddingMetadata,
    ) -> QdrantUpsertReport:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        vector_size = len(vectors[0]) if vectors else embedding_metadata.dimension
        self.ensure_collection(vector_size=vector_size)
        points = build_qdrant_points(chunks, vectors, embedding_metadata)
        self.client.upsert(collection_name=self.collection_name, points=_point_structs(points))
        return QdrantUpsertReport(
            collection_name=self.collection_name,
            points_count=len(points),
            vector_size=vector_size,
        )

    def search(
        self,
        query_vector: list[float],
        *,
        limit: int = 5,
        filters: QdrantSearchFilters | None = None,
    ) -> list[RetrievalResult]:
        if limit <= 0 or not query_vector:
            return []
        query_filter = build_qdrant_filter(filters or QdrantSearchFilters())
        client = self.client
        if hasattr(client, "search"):
            hits = client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
            )
        else:
            response = client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
            )
            hits = getattr(response, "points", response)
        return [_retrieval_result_from_hit(hit) for hit in hits]


def build_qdrant_points(
    chunks: list[DocumentChunk],
    vectors: list[list[float]],
    embedding_metadata: EmbeddingMetadata,
) -> list[dict[str, object]]:
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors must have the same length")
    points = []
    for chunk, vector in zip(chunks, vectors, strict=False):
        points.append(
            {
                "id": str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                "vector": vector,
                "payload": {
                    **chunk.payload(),
                    **embedding_metadata.payload(),
                },
            }
        )
    return points


def build_filter_conditions(filters: QdrantSearchFilters) -> list[dict[str, str]]:
    values = {
        "contract_key_canon": filters.contract_key_canon,
        "source": filters.source,
        "document_type": filters.document_type,
    }
    return [
        {"key": key, "value": value}
        for key, value in values.items()
        if value is not None and value != ""
    ]


def build_qdrant_filter(filters: QdrantSearchFilters) -> Any | None:
    conditions = build_filter_conditions(filters)
    if not conditions:
        return None
    try:
        models = _qdrant_models()
    except ImportError:
        return {
            "must": [
                {"key": item["key"], "match": {"value": item["value"]}} for item in conditions
            ]
        }
    return models.Filter(
        must=[
            models.FieldCondition(
                key=item["key"],
                match=models.MatchValue(value=item["value"]),
            )
            for item in conditions
        ]
    )


def _collection_exists(client: Any, collection_name: str) -> bool:
    if hasattr(client, "collection_exists"):
        return bool(client.collection_exists(collection_name=collection_name))
    try:
        client.get_collection(collection_name=collection_name)
    except Exception:
        return False
    return True


def _point_structs(points: list[dict[str, object]]) -> list[Any]:
    try:
        models = _qdrant_models()
    except ImportError:
        return points
    return [models.PointStruct(**point) for point in points]


def _qdrant_models() -> Any:
    try:
        from qdrant_client import models
    except ImportError as exc:
        raise ImportError(
            "qdrant-client is required for Qdrant operations. "
            'Install it with: python -m pip install -e ".[rag]"'
        ) from exc
    return models


def _retrieval_result_from_hit(hit: Any) -> RetrievalResult:
    payload = _hit_value(hit, "payload") or {}
    score = _hit_value(hit, "score")
    return RetrievalResult(chunk=_chunk_from_payload(payload), score=float(score or 0.0))


def _chunk_from_payload(payload: dict[str, Any]) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=str(payload.get("chunk_id", "")),
        document_id=str(payload.get("document_id", "")),
        text=str(payload.get("text", "")),
        chunk_index=int(payload.get("chunk_index", 0)),
        contract_key_canon=payload.get("contract_key_canon"),
        source=payload.get("source"),
        source_record_id=payload.get("source_record_id"),
        document_type=str(payload.get("document_type", "text")),
        text_hash=payload.get("text_hash"),
    )


def _hit_value(hit: Any, key: str) -> Any:
    if isinstance(hit, dict):
        return hit.get(key)
    return getattr(hit, key, None)
