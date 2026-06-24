from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .document_loader import load_document
from .schemas import DocumentRef
from .source_registry import build_agent4_capabilities, build_agent4_source_registry_summary

AGENT4_DOCUMENTS_MANIFEST = "agent4_documents_manifest"
AGENT4_DOCUMENTS_MANIFEST_VERSION = "0.1.0"
DEFAULT_SYNTHETIC_CORPUS_INDEX = Path("data/synthetic/agent4_corpus/agent4_corpus_index.json")
DEFAULT_DOCUMENTS_MANIFEST_PATH = Path("data/processed/agent4_documents_manifest.json")


@dataclass(frozen=True, slots=True)
class CorpusDocumentSpec:
    path: Path
    source: str
    contract_key_canon: str | None = None
    source_record_id: str | None = None
    document_type: str | None = None


def load_corpus_index(
    index_path: Path = DEFAULT_SYNTHETIC_CORPUS_INDEX,
) -> list[CorpusDocumentSpec]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    base_dir = index_path.parent
    specs = []
    for item in payload.get("documents", []):
        specs.append(
            CorpusDocumentSpec(
                path=base_dir / item["path"],
                source=item["source"],
                contract_key_canon=item.get("contract_key_canon"),
                source_record_id=item.get("source_record_id"),
                document_type=item.get("document_type"),
            )
        )
    return specs


def load_corpus_documents(
    index_path: Path = DEFAULT_SYNTHETIC_CORPUS_INDEX,
) -> list[DocumentRef]:
    documents = []
    for spec in load_corpus_index(index_path):
        documents.append(
            load_document(
                spec.path,
                source=spec.source,
                contract_key_canon=spec.contract_key_canon,
                source_record_id=spec.source_record_id,
                document_type=spec.document_type,
            )
        )
    return documents


def build_documents_manifest(
    documents: list[DocumentRef],
    *,
    corpus_index_path: Path | None = None,
) -> dict[str, Any]:
    capabilities = build_agent4_capabilities()
    return {
        "dataset": AGENT4_DOCUMENTS_MANIFEST,
        "version": AGENT4_DOCUMENTS_MANIFEST_VERSION,
        "corpus_index": str(corpus_index_path) if corpus_index_path else None,
        "agent4_scope": capabilities["scope"],
        "document_source_policy": capabilities["document_source_policy"],
        "implemented_in_mvp": capabilities["implemented_in_mvp"],
        "not_implemented_in_mvp": capabilities["not_implemented_in_mvp"],
        "official_source_registry": build_agent4_source_registry_summary(),
        "documents_count": len(documents),
        "documents": [document.manifest_record() for document in documents],
    }


def write_documents_manifest(
    documents: list[DocumentRef],
    output_path: Path = DEFAULT_DOCUMENTS_MANIFEST_PATH,
    *,
    corpus_index_path: Path | None = None,
) -> dict[str, Any]:
    manifest = build_documents_manifest(documents, corpus_index_path=corpus_index_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
