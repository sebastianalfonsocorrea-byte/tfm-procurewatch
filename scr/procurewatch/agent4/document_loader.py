from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

from .schemas import DocumentRef

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - depends on optional local dependency.
    BeautifulSoup = None

_WHITESPACE_RE = re.compile(r"\s+")


def load_text_document(
    path: Path,
    *,
    source: str = "local",
    contract_key_canon: str | None = None,
    source_record_id: str | None = None,
    document_type: str = "text",
    encoding: str = "utf-8",
) -> DocumentRef:
    text = path.read_text(encoding=encoding)
    return _build_document_ref(
        path,
        text,
        source=source,
        contract_key_canon=contract_key_canon,
        source_record_id=source_record_id,
        document_type=document_type,
        encoding=encoding,
    )


def load_markdown_document(
    path: Path,
    *,
    source: str = "local",
    contract_key_canon: str | None = None,
    source_record_id: str | None = None,
    encoding: str = "utf-8",
) -> DocumentRef:
    return load_text_document(
        path,
        source=source,
        contract_key_canon=contract_key_canon,
        source_record_id=source_record_id,
        document_type="markdown",
        encoding=encoding,
    )


def load_html_document(
    path: Path,
    *,
    source: str = "local",
    contract_key_canon: str | None = None,
    source_record_id: str | None = None,
    encoding: str = "utf-8",
) -> DocumentRef:
    html = path.read_text(encoding=encoding)
    text, parser_name = _extract_html_text(html)
    document = _build_document_ref(
        path,
        text,
        source=source,
        contract_key_canon=contract_key_canon,
        source_record_id=source_record_id,
        document_type="html",
        encoding=encoding,
    )
    return DocumentRef(
        document_id=document.document_id,
        source=document.source,
        text=document.text,
        contract_key_canon=document.contract_key_canon,
        source_record_id=document.source_record_id,
        document_type=document.document_type,
        text_hash=document.text_hash,
        metadata={**document.metadata, "html_parser": parser_name},
    )


def load_document(
    path: Path,
    *,
    source: str = "local",
    contract_key_canon: str | None = None,
    source_record_id: str | None = None,
    document_type: str | None = None,
    encoding: str = "utf-8",
) -> DocumentRef:
    resolved_type = document_type or _document_type_from_suffix(path)
    if resolved_type == "html":
        return load_html_document(
            path,
            source=source,
            contract_key_canon=contract_key_canon,
            source_record_id=source_record_id,
            encoding=encoding,
        )
    if resolved_type == "markdown":
        return load_markdown_document(
            path,
            source=source,
            contract_key_canon=contract_key_canon,
            source_record_id=source_record_id,
            encoding=encoding,
        )
    return load_text_document(
        path,
        source=source,
        contract_key_canon=contract_key_canon,
        source_record_id=source_record_id,
        document_type=resolved_type,
        encoding=encoding,
    )


def _build_document_ref(
    path: Path,
    text: str,
    *,
    source: str,
    contract_key_canon: str | None,
    source_record_id: str | None,
    document_type: str,
    encoding: str,
) -> DocumentRef:
    text_hash = hashlib.sha256(text.encode(encoding)).hexdigest()
    document_id = f"{path.stem}-{text_hash[:16]}"
    return DocumentRef(
        document_id=document_id,
        source=source,
        text=text,
        contract_key_canon=contract_key_canon,
        source_record_id=source_record_id,
        document_type=document_type,
        text_hash=text_hash,
        metadata={"path": str(path), "text_hash": text_hash},
    )


def _document_type_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    return "text"


def _extract_html_text(html: str) -> tuple[str, str]:
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style"]):
            element.decompose()
        return _normalize_whitespace(soup.get_text(" ", strip=True)), "beautifulsoup"

    parser = _HTMLTextExtractor()
    parser.feed(html)
    parser.close()
    return _normalize_whitespace(" ".join(parser.parts)), "html.parser"


def _normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)
