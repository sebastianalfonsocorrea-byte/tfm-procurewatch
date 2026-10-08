from __future__ import annotations

import re

from .schemas import DocumentChunk, RetrievalResult

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def keyword_retrieve(
    chunks: list[DocumentChunk],
    query: str,
    *,
    limit: int = 5,
) -> list[RetrievalResult]:
    if limit <= 0 or not chunks:
        return []

    terms = {term.lower() for term in _TOKEN_RE.findall(query)}
    if not terms:
        return []

    scored: list[RetrievalResult] = []
    for chunk in chunks:
        text = chunk.text.lower()
        matches = sum(1 for term in terms if term in text)
        if matches:
            scored.append(RetrievalResult(chunk=chunk, score=matches / len(terms)))

    return sorted(
        scored,
        key=lambda item: (-(item.score or 0.0), item.chunk.chunk_id),
    )[:limit]
