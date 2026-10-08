from __future__ import annotations

import hashlib
import re

from .schemas import DocumentChunk, DocumentRef

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def chunk_text(
    document: DocumentRef,
    *,
    chunk_size: int = 900,
    overlap: int = 120,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = normalize_text(document.text)
    if not text:
        return []

    chunks: list[DocumentChunk] = []
    start = 0
    index = 0
    step = chunk_size - overlap
    while start < len(text):
        chunk_body = text[start : start + chunk_size].strip()
        text_hash = hashlib.sha256(chunk_body.encode("utf-8")).hexdigest()
        chunks.append(
            DocumentChunk(
                chunk_id=f"{document.document_id}:{index}",
                document_id=document.document_id,
                text=chunk_body,
                chunk_index=index,
                contract_key_canon=document.contract_key_canon,
                source=document.source,
                source_record_id=document.source_record_id,
                document_type=document.document_type,
                text_hash=text_hash,
            )
        )
        index += 1
        start += step

    return chunks
