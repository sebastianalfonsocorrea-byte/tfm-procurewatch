from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DocumentRef:
    document_id: str
    source: str
    text: str
    contract_key_canon: str | None = None
    source_record_id: str | None = None
    document_type: str = "text"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    text: str
    chunk_index: int
    contract_key_canon: str | None = None
    source: str | None = None
    source_record_id: str | None = None
    document_type: str = "text"
    text_hash: str | None = None

    def payload(self) -> dict[str, str | int | None]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "contract_key_canon": self.contract_key_canon,
            "source": self.source,
            "source_record_id": self.source_record_id,
            "document_type": self.document_type,
            "text": self.text,
            "text_hash": self.text_hash,
            "chunk_index": self.chunk_index,
        }


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    chunk: DocumentChunk
    score: float | None = None
