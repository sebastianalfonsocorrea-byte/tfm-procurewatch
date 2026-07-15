from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_EMBEDDING_MODEL = "bge-m3"
DETERMINISTIC_TEST_EMBEDDING_MODEL = "deterministic-test-embedding"


@dataclass(frozen=True, slots=True)
class EmbeddingMetadata:
    provider: str
    model: str
    dimension: int
    indexed_at: str

    def payload(self) -> dict[str, str | int]:
        return {
            "embedding_provider": self.provider,
            "embedding_model": self.model,
            "embedding_dimension": self.dimension,
            "indexed_at": self.indexed_at,
        }


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    metadata: EmbeddingMetadata


class OllamaEmbeddingClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_EMBEDDING_MODEL,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed_texts(self, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(vectors=[], metadata=self._metadata(0))

        response = self._post_json(
            "/api/embed",
            {
                "model": self.model,
                "input": texts,
            },
        )
        vectors = _coerce_vectors(response.get("embeddings", []))
        if len(vectors) != len(texts):
            raise ValueError("Ollama returned a different number of embeddings than inputs")
        dimension = len(vectors[0]) if vectors else 0
        return EmbeddingBatch(vectors=vectors, metadata=self._metadata(dimension))

    def embed_query(self, query: str) -> EmbeddingBatch:
        return self.embed_texts([query])

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError) as exc:
            raise ConnectionError(f"Ollama embeddings endpoint is not reachable: {exc}") from exc

    def _metadata(self, dimension: int) -> EmbeddingMetadata:
        return EmbeddingMetadata(
            provider="ollama",
            model=self.model,
            dimension=dimension,
            indexed_at=_utc_now(),
        )


class DeterministicEmbeddingClient:
    def __init__(self, *, dimension: int = 16) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than 0")
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> EmbeddingBatch:
        vectors = [_deterministic_vector(text, self.dimension) for text in texts]
        return EmbeddingBatch(
            vectors=vectors,
            metadata=EmbeddingMetadata(
                provider="deterministic",
                model=DETERMINISTIC_TEST_EMBEDDING_MODEL,
                dimension=self.dimension,
                indexed_at=_utc_now(),
            ),
        )

    def embed_query(self, query: str) -> EmbeddingBatch:
        return self.embed_texts([query])


def _coerce_vectors(value: object) -> list[list[float]]:
    if not isinstance(value, list):
        raise ValueError("Ollama embeddings response must contain a list")
    vectors: list[list[float]] = []
    for vector in value:
        if not isinstance(vector, list):
            raise ValueError("Each embedding must be a list")
        vectors.append([float(item) for item in vector])
    return vectors


def _deterministic_vector(text: str, dimension: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    while len(values) < dimension:
        for byte in digest:
            values.append((byte / 127.5) - 1.0)
            if len(values) == dimension:
                break
        digest = hashlib.sha256(digest).digest()
    return values


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
