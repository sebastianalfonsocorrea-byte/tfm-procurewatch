from __future__ import annotations

from .schemas import DocumentChunk, RetrievalResult


def keyword_retrieve(
    chunks: list[DocumentChunk],
    query: str,
    *,
    limit: int = 5,
) -> list[RetrievalResult]:
    terms = {term.lower() for term in query.split() if term.strip()}
    if not terms:
        return []

    scored: list[RetrievalResult] = []
    for chunk in chunks:
        text = chunk.text.lower()
        matches = sum(1 for term in terms if term in text)
        if matches:
            scored.append(RetrievalResult(chunk=chunk, score=matches / len(terms)))

    return sorted(scored, key=lambda item: item.score or 0.0, reverse=True)[:limit]
