from __future__ import annotations

import hashlib
from pathlib import Path

from .schemas import DocumentRef


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
    digest = hashlib.sha256(text.encode(encoding)).hexdigest()[:16]
    document_id = f"{path.stem}-{digest}"
    return DocumentRef(
        document_id=document_id,
        source=source,
        text=text,
        contract_key_canon=contract_key_canon,
        source_record_id=source_record_id,
        document_type=document_type,
        metadata={"path": str(path)},
    )
