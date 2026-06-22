from __future__ import annotations

import json
from pathlib import Path

from .chunking import chunk_text
from .corpus import DEFAULT_SYNTHETIC_CORPUS_INDEX, load_corpus_documents
from .retrieval import keyword_retrieve
from .schemas import DocumentChunk, RetrievalResult
from .state import Agent4State


def load_contract_context_node(state: Agent4State) -> Agent4State:
    contract_key = state.get("contract_key_canon")
    source_record_id = state.get("source_record_id")
    context = dict(state.get("contract_context", {}))
    if contract_key and "contract_key_canon" not in context:
        context["contract_key_canon"] = contract_key
    if source_record_id and "source_record_id" not in context:
        context["source_record_id"] = source_record_id
    warnings = _warnings(state)
    if not contract_key:
        warnings.append("No se ha indicado contract_key_canon para filtrar documentos.")
    return {**state, "contract_context": context, "warnings": warnings}


def discover_documents_node(state: Agent4State) -> Agent4State:
    if state.get("document_refs"):
        return state

    corpus_index = state.get("corpus_index", DEFAULT_SYNTHETIC_CORPUS_INDEX)
    documents = load_corpus_documents(Path(corpus_index))
    contract_key = state.get("contract_key_canon")
    if contract_key:
        documents = [
            document for document in documents if document.contract_key_canon == contract_key
        ]

    warnings = _warnings(state)
    if not documents:
        warnings.append("No se han encontrado documentos para el contrato solicitado.")
    return {**state, "document_refs": documents, "warnings": warnings}


def extract_text_node(state: Agent4State) -> Agent4State:
    documents = []
    warnings = _warnings(state)
    for document in state.get("document_refs", []):
        if document.text.strip():
            documents.append(document)
        else:
            warnings.append(f"Documento sin texto util: {document.document_id}")
    return {**state, "document_refs": documents, "warnings": warnings}


def chunk_documents_node(state: Agent4State) -> Agent4State:
    chunks: list[DocumentChunk] = []
    chunk_size = int(state.get("chunk_size", 900))
    overlap = int(state.get("overlap", 120))
    for document in state.get("document_refs", []):
        chunks.extend(chunk_text(document, chunk_size=chunk_size, overlap=overlap))
    warnings = _warnings(state)
    if not chunks:
        warnings.append("No se han generado chunks documentales.")
    return {**state, "chunks": chunks, "warnings": warnings}


def embed_and_upsert_node(state: Agent4State) -> Agent4State:
    chunks = state.get("chunks", [])
    if not chunks:
        return state

    embedding_client = state.get("embedding_client")
    vector_store = state.get("vector_store")
    warnings = _warnings(state)
    if embedding_client is None or vector_store is None:
        warnings.append("Vector store no configurado; se usara retrieval local por keyword.")
        return {**state, "warnings": warnings}

    try:
        batch = embedding_client.embed_texts([chunk.text for chunk in chunks])
        report = vector_store.upsert_chunks(chunks, batch.vectors, batch.metadata)
    except Exception as exc:
        warnings.append(f"No se pudo indexar en vector store: {exc}")
        return {**state, "warnings": warnings}

    return {
        **state,
        "warnings": warnings,
        "embedding_metadata": batch.metadata.payload(),
        "vector_upsert_report": {
            "collection_name": report.collection_name,
            "points_count": report.points_count,
            "vector_size": report.vector_size,
        },
    }


def retrieve_context_node(state: Agent4State) -> Agent4State:
    if state.get("retrieved_context"):
        return state

    question = state.get("question", "")
    warnings = _warnings(state)
    if not question.strip():
        warnings.append("No hay pregunta para recuperar contexto documental.")
        return {**state, "retrieved_context": [], "warnings": warnings}

    retrieved_context = _vector_retrieve_if_available(state)
    if retrieved_context is None:
        retrieved_context = keyword_retrieve(
            state.get("chunks", []),
            question,
            limit=int(state.get("retrieval_limit", 5)),
        )

    if not retrieved_context:
        warnings.append("No hay evidencia documental recuperada para responder con trazabilidad.")
    return {**state, "retrieved_context": retrieved_context, "warnings": warnings}


def generate_case_context_node(state: Agent4State) -> Agent4State:
    retrieved = state.get("retrieved_context", [])
    citations = _build_citations(retrieved)
    warnings = _warnings(state)
    if not retrieved:
        answer = (
            "No hay evidencia documental suficiente para generar contexto trazable. "
            "No se declara fraude."
        )
    else:
        answer = (
            f"Se han recuperado {len(retrieved)} evidencias documentales para revision humana. "
            "No se declara fraude; el resultado solo resume contexto textual recuperado."
        )
    return {**state, "answer": answer, "citations": citations, "warnings": warnings}


def persist_agent_output_node(state: Agent4State) -> Agent4State:
    output = _agent_output(state)
    output_path = state.get("output_path")
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**state, "agent_output": output}


def require_evidence_node(state: Agent4State) -> Agent4State:
    if state.get("retrieved_context"):
        return state
    warnings = _warnings(state)
    warning = "No hay evidencia documental recuperada para responder con trazabilidad."
    if warning not in warnings:
        warnings.append(warning)
    return {**state, "warnings": warnings}


def _vector_retrieve_if_available(state: Agent4State) -> list[RetrievalResult] | None:
    embedding_client = state.get("embedding_client")
    vector_store = state.get("vector_store")
    if embedding_client is None or vector_store is None:
        return None
    try:
        batch = embedding_client.embed_query(state.get("question", ""))
        vector = batch.vectors[0] if batch.vectors else []
        return vector_store.search(vector, limit=int(state.get("retrieval_limit", 5)))
    except Exception:
        return None


def _build_citations(results: list[RetrievalResult]) -> list[str]:
    return [
        f"document_id={result.chunk.document_id}; chunk_id={result.chunk.chunk_id}"
        for result in results
    ]


def _agent_output(state: Agent4State) -> dict[str, object]:
    return {
        "run_id": state.get("run_id"),
        "contract_key_canon": state.get("contract_key_canon"),
        "question": state.get("question"),
        "answer": state.get("answer"),
        "citations": state.get("citations", []),
        "warnings": state.get("warnings", []),
        "retrieved_context": [
            {
                "chunk_id": result.chunk.chunk_id,
                "document_id": result.chunk.document_id,
                "contract_key_canon": result.chunk.contract_key_canon,
                "score": result.score,
                "text": result.chunk.text,
            }
            for result in state.get("retrieved_context", [])
        ],
        "contract_context": state.get("contract_context", {}),
        "embedding_metadata": state.get("embedding_metadata", {}),
        "vector_upsert_report": state.get("vector_upsert_report", {}),
    }


def _warnings(state: Agent4State) -> list[str]:
    return list(state.get("warnings", []))
