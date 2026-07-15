from __future__ import annotations

import json
from pathlib import Path

from .chunking import chunk_text
from .corpus import DEFAULT_SYNTHETIC_CORPUS_INDEX, load_corpus_documents
from .prompts import CASE_CONTEXT_PROMPT, build_case_context_prompt
from .qdrant_store import QdrantSearchFilters
from .retrieval import keyword_retrieve
from .schemas import DocumentChunk, RetrievalResult
from .source_registry import build_agent4_capabilities, build_agent4_source_registry_summary
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

    active_embedding_client = embedding_client
    try:
        batch = embedding_client.embed_texts([chunk.text for chunk in chunks])
    except Exception as exc:
        fallback_client = state.get("embedding_fallback_client")
        if fallback_client is None:
            warnings.append(f"No se pudo generar embeddings para vector store: {exc}")
            return {**state, "warnings": warnings}
        warnings.append(
            f"No se pudo usar el modelo de embeddings principal: {exc}. "
            "Se usara embedding determinista local para Qdrant."
        )
        try:
            batch = fallback_client.embed_texts([chunk.text for chunk in chunks])
            active_embedding_client = fallback_client
        except Exception as fallback_exc:
            warnings.append(f"No se pudo generar embeddings fallback: {fallback_exc}")
            return {**state, "warnings": warnings}

    try:
        report = vector_store.upsert_chunks(chunks, batch.vectors, batch.metadata)
    except Exception as exc:
        warnings.append(f"No se pudo indexar en vector store: {exc}")
        return {**state, "warnings": warnings}

    return {
        **state,
        "warnings": warnings,
        "active_embedding_client": active_embedding_client,
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

    retrieved_context, vector_warning = _vector_retrieve_if_available(state)
    if vector_warning is not None:
        warnings.append(vector_warning)
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
    warnings = _warnings(state)
    if not retrieved:
        warning = "No hay evidencia documental recuperada para responder con trazabilidad."
        if warning not in warnings:
            warnings.append(warning)
    citations = _build_citations(retrieved)
    evidences = [_evidence_record(result) for result in retrieved]
    llm_answer, generation_metadata = _generate_llm_answer_if_available(
        state,
        evidences,
        citations,
        warnings,
    )
    case_context = _build_case_context(
        state,
        evidences,
        citations,
        warnings,
        generated_answer=llm_answer,
        generation_metadata=generation_metadata,
    )
    return {
        **state,
        "answer": str(case_context["summary"]),
        "citations": citations,
        "case_context": case_context,
        "warnings": warnings,
    }


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


def _vector_retrieve_if_available(
    state: Agent4State,
) -> tuple[list[RetrievalResult] | None, str | None]:
    embedding_client = state.get("active_embedding_client") or state.get("embedding_client")
    vector_store = state.get("vector_store")
    if embedding_client is None or vector_store is None:
        return None, None
    try:
        batch = embedding_client.embed_query(state.get("question", ""))
    except Exception as exc:
        fallback_client = state.get("embedding_fallback_client")
        if fallback_client is None or fallback_client is embedding_client:
            return None, f"No se pudo generar embedding de consulta para Qdrant: {exc}"
        try:
            batch = fallback_client.embed_query(state.get("question", ""))
        except Exception as fallback_exc:
            return None, f"No se pudo generar embedding fallback de consulta: {fallback_exc}"

    try:
        vector = batch.vectors[0] if batch.vectors else []
        filters = QdrantSearchFilters(contract_key_canon=state.get("contract_key_canon"))
        return (
            vector_store.search(
                vector,
                limit=int(state.get("retrieval_limit", 5)),
                filters=filters,
            ),
            None,
        )
    except Exception as exc:
        return None, f"No se pudo recuperar contexto desde Qdrant: {exc}"


def _build_citations(results: list[RetrievalResult]) -> list[str]:
    return [
        (
            f"document_id={result.chunk.document_id}; "
            f"chunk_id={result.chunk.chunk_id}; "
            f"contract_key_canon={result.chunk.contract_key_canon or ''}"
        )
        for result in results
    ]


def _build_case_context(
    state: Agent4State,
    evidences: list[dict[str, object]],
    citations: list[str],
    warnings: list[str],
    *,
    generated_answer: str | None = None,
    generation_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    generation = {
        "mode": "deterministic_fallback",
        "prompt_policy": CASE_CONTEXT_PROMPT.strip(),
        "llm_model": None,
    }
    if generation_metadata:
        generation.update(generation_metadata)
    capabilities = build_agent4_capabilities()
    return {
        "schema_version": "agent4_case_context_v1",
        "contract_key_canon": state.get("contract_key_canon"),
        "question": state.get("question"),
        "summary": generated_answer or _case_summary(state, evidences),
        "agent4_scope": capabilities["scope"],
        "document_source_policy": capabilities["document_source_policy"],
        "implemented_in_mvp": capabilities["implemented_in_mvp"],
        "not_implemented_in_mvp": capabilities["not_implemented_in_mvp"],
        "official_source_registry": build_agent4_source_registry_summary(),
        "evidences": evidences,
        "citations": citations,
        "warnings": warnings,
        "contract_fields_used": _used_fields(state.get("contract_context", {})),
        "agent2_score": _agent2_score_fields(state.get("agent2_score", {})),
        "agent3_metrics_used": _used_fields(state.get("agent3_metrics", {})),
        "generation": generation,
        "decision_boundary": (
            "No se declara fraude; Agent4 resume evidencia documental para revision humana."
        ),
    }


def _generate_llm_answer_if_available(
    state: Agent4State,
    evidences: list[dict[str, object]],
    citations: list[str],
    warnings: list[str],
) -> tuple[str | None, dict[str, object]]:
    if not evidences:
        return None, {"fallback_reason": "no_evidence"}

    generation_client = state.get("generation_client")
    if generation_client is None:
        return None, {"fallback_reason": "generation_client_not_configured"}

    prompt = build_case_context_prompt(
        question=state.get("question", ""),
        contract_context=state.get("contract_context", {}),
        evidences=evidences,
        citations=citations,
    )
    try:
        result = generation_client.generate(prompt)
        text = _ensure_decision_boundary(_clean_llm_text(getattr(result, "text", str(result))))
        return text, {
            "mode": getattr(result, "provider", getattr(generation_client, "provider", "llm")),
            "provider": getattr(result, "provider", getattr(generation_client, "provider", None)),
            "llm_model": getattr(result, "model", getattr(generation_client, "model", None)),
            "fallback_reason": None,
        }
    except Exception as exc:
        warnings.append(f"No se pudo generar ficha con Ollama: {exc}")
        return None, {"fallback_reason": "llm_generation_failed"}


def _evidence_record(result: RetrievalResult) -> dict[str, object]:
    chunk = result.chunk
    return {
        "document_id": chunk.document_id,
        "chunk_id": chunk.chunk_id,
        "contract_key_canon": chunk.contract_key_canon,
        "source": chunk.source,
        "source_record_id": chunk.source_record_id,
        "document_type": chunk.document_type,
        "score": result.score,
        "text_excerpt": _excerpt(chunk.text),
    }


def _case_summary(state: Agent4State, evidences: list[dict[str, object]]) -> str:
    contract_key = state.get("contract_key_canon") or "contrato sin clave canonica"
    if not evidences:
        return (
            f"No hay evidencia documental suficiente para generar una ficha trazable de "
            f"{contract_key}. No se declara fraude."
        )
    return (
        f"Se han recuperado {len(evidences)} evidencias documentales para {contract_key}. "
        "La ficha resume contexto textual recuperado para revision humana. "
        "No se declara fraude."
    )


def _used_fields(values: object) -> dict[str, object]:
    if not isinstance(values, dict):
        return {}
    return {key: value for key, value in sorted(values.items()) if _has_value(value)}


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return True


def _excerpt(text: str, *, max_chars: int = 500) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _clean_llm_text(text: str) -> str:
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return " ".join(text.split()).strip()


def _ensure_decision_boundary(text: str) -> str:
    boundary = "No se declara fraude."
    if boundary.lower() in text.lower():
        return text
    return f"{text} {boundary}".strip()


def _agent_output(state: Agent4State) -> dict[str, object]:
    capabilities = build_agent4_capabilities()
    return {
        "run_id": state.get("run_id"),
        "contract_key_canon": state.get("contract_key_canon"),
        "question": state.get("question"),
        "agent4_scope": capabilities["scope"],
        "document_source_policy": capabilities["document_source_policy"],
        "answer": state.get("answer"),
        "citations": state.get("citations", []),
        "warnings": state.get("warnings", []),
        "case_context": state.get("case_context", {}),
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
        "agent2_score": state.get("agent2_score", {}),
        "embedding_metadata": state.get("embedding_metadata", {}),
        "vector_upsert_report": state.get("vector_upsert_report", {}),
    }


def _warnings(state: Agent4State) -> list[str]:
    return list(state.get("warnings", []))


def _agent2_score_fields(values: object) -> dict[str, object]:
    if not isinstance(values, dict):
        return {}
    return {
        key: value
        for key, value in sorted(values.items())
        if value is not None and not (isinstance(value, str) and not value.strip())
    }
