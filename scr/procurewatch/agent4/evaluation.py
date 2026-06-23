from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .corpus import DEFAULT_SYNTHETIC_CORPUS_INDEX
from .graph import run_agent4_case_flow
from .qdrant_store import DEFAULT_QDRANT_COLLECTION

DEFAULT_AGENT4_EVAL_SET_PATH = Path("data/synthetic/agent4_corpus/agent4_eval_set.json")
DEFAULT_AGENT4_EVALUATION_REPORT_PATH = Path("data/processed/agent4_evaluation_report.json")
AGENT4_EVALUATION_SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class Agent4EvalCase:
    case_id: str
    contract_key_canon: str
    question: str
    expected_document_ids: tuple[str, ...] = ()
    expected_terms: tuple[str, ...] = ()
    expect_evidence: bool = True


def load_agent4_eval_cases(path: Path = DEFAULT_AGENT4_EVAL_SET_PATH) -> list[Agent4EvalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for item in payload.get("cases", []):
        cases.append(
            Agent4EvalCase(
                case_id=str(item["case_id"]),
                contract_key_canon=str(item["contract_key_canon"]),
                question=str(item["question"]),
                expected_document_ids=tuple(
                    str(value) for value in item.get("expected_document_ids", [])
                ),
                expected_terms=tuple(str(value) for value in item.get("expected_terms", [])),
                expect_evidence=bool(item.get("expect_evidence", True)),
            )
        )
    return cases


def run_agent4_evaluation(
    *,
    eval_set_path: Path = DEFAULT_AGENT4_EVAL_SET_PATH,
    corpus_index: Path = DEFAULT_SYNTHETIC_CORPUS_INDEX,
    output_path: Path = DEFAULT_AGENT4_EVALUATION_REPORT_PATH,
    use_services: bool = False,
    qdrant_url: str | None = None,
    collection_name: str = DEFAULT_QDRANT_COLLECTION,
    ollama_base_url: str | None = None,
    embedding_model: str | None = None,
    llm_model: str | None = None,
    chunk_size: int = 900,
    overlap: int = 120,
    retrieval_limit: int = 5,
) -> dict[str, Any]:
    cases = load_agent4_eval_cases(eval_set_path)
    case_reports = []
    for case in cases:
        state = run_agent4_case_flow(
            contract_key_canon=case.contract_key_canon,
            question=case.question,
            corpus_index=corpus_index,
            use_services=use_services,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            ollama_base_url=ollama_base_url,
            embedding_model=embedding_model,
            llm_model=llm_model,
            chunk_size=chunk_size,
            overlap=overlap,
            retrieval_limit=retrieval_limit,
        )
        case_reports.append(evaluate_agent4_case_state(case, state))

    report = build_agent4_evaluation_report(
        case_reports,
        eval_set_path=eval_set_path,
        corpus_index=corpus_index,
        use_services=use_services,
        retrieval_limit=retrieval_limit,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def evaluate_agent4_case_state(
    case: Agent4EvalCase,
    state: dict[str, Any],
) -> dict[str, Any]:
    retrieved = list(state.get("retrieved_context", []))
    citations = [str(value) for value in state.get("citations", [])]
    expected_documents = set(case.expected_document_ids)
    retrieved_document_ids = [_retrieval_document_id(result) for result in retrieved]
    retrieved_document_ids = [value for value in retrieved_document_ids if value]
    unique_retrieved_documents = sorted(set(retrieved_document_ids))
    matching_documents = sorted(expected_documents & set(unique_retrieved_documents))
    relevant_results = sum(
        1 for document_id in retrieved_document_ids if document_id in expected_documents
    )
    evidence_count = len(retrieved)
    has_evidence = evidence_count > 0
    expected_terms_found = _expected_terms_found(case.expected_terms, retrieved)

    if expected_documents:
        precision_at_k = _ratio(relevant_results, evidence_count) if evidence_count else 0.0
        expected_document_recall = _ratio(len(matching_documents), len(expected_documents))
    else:
        precision_at_k = None
        expected_document_recall = None

    return {
        "case_id": case.case_id,
        "contract_key_canon": case.contract_key_canon,
        "question": case.question,
        "expect_evidence": case.expect_evidence,
        "has_evidence": has_evidence,
        "expectation_met": has_evidence == case.expect_evidence,
        "evidence_count": evidence_count,
        "citation_count": len(citations),
        "citation_coverage_ratio": _citation_coverage(retrieved, citations),
        "precision_at_k": precision_at_k,
        "expected_document_recall": expected_document_recall,
        "expected_terms": list(case.expected_terms),
        "expected_terms_found": expected_terms_found,
        "expected_term_coverage_ratio": _ratio(len(expected_terms_found), len(case.expected_terms))
        if case.expected_terms
        else None,
        "expected_document_ids": list(case.expected_document_ids),
        "retrieved_document_ids": unique_retrieved_documents,
        "matching_document_ids": matching_documents,
        "warnings": [str(value) for value in state.get("warnings", [])],
    }


def build_agent4_evaluation_report(
    case_reports: list[dict[str, Any]],
    *,
    eval_set_path: Path,
    corpus_index: Path,
    use_services: bool,
    retrieval_limit: int,
) -> dict[str, Any]:
    total_cases = len(case_reports)
    cases_with_evidence = sum(1 for case in case_reports if case["has_evidence"])
    expectations_met = sum(1 for case in case_reports if case["expectation_met"])
    total_warnings = sum(len(case["warnings"]) for case in case_reports)
    return {
        "dataset": "agent4_evaluation_report",
        "schema_version": AGENT4_EVALUATION_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "eval_set_path": str(eval_set_path),
        "corpus_index": str(corpus_index),
        "mode": "services" if use_services else "offline",
        "retrieval_limit": retrieval_limit,
        "summary": {
            "cases_count": total_cases,
            "cases_with_evidence": cases_with_evidence,
            "evidence_case_ratio": _ratio(cases_with_evidence, total_cases),
            "expectation_accuracy": _ratio(expectations_met, total_cases),
            "average_citation_coverage": _average_metric(case_reports, "citation_coverage_ratio"),
            "average_precision_at_k": _average_metric(case_reports, "precision_at_k"),
            "average_expected_document_recall": _average_metric(
                case_reports,
                "expected_document_recall",
            ),
            "average_expected_term_coverage": _average_metric(
                case_reports,
                "expected_term_coverage_ratio",
            ),
            "warnings_count": total_warnings,
        },
        "ragas": {
            "status": "not_run",
            "reason": "Corpus sintetico demasiado pequeno para metricas RAGAS representativas.",
        },
        "limitations": [
            "La evaluacion local mide trazabilidad y retrieval, no correccion juridica.",
            "El corpus sintetico no representa la variabilidad documental real.",
            "Agent4 no declara fraude; solo resume evidencia para revision humana.",
        ],
        "cases": case_reports,
    }


def _retrieval_document_id(result: object) -> str | None:
    chunk = getattr(result, "chunk", None)
    document_id = getattr(chunk, "document_id", None)
    return str(document_id) if document_id else None


def _retrieval_text(result: object) -> str:
    chunk = getattr(result, "chunk", None)
    text = getattr(chunk, "text", "")
    return str(text)


def _expected_terms_found(expected_terms: tuple[str, ...], retrieved: list[object]) -> list[str]:
    text = " ".join(_retrieval_text(result).lower() for result in retrieved)
    return sorted({term for term in expected_terms if term.lower() in text})


def _citation_coverage(retrieved: list[object], citations: list[str]) -> float | None:
    if not retrieved:
        return None
    citation_text = "\n".join(citations)
    covered = 0
    for result in retrieved:
        chunk = getattr(result, "chunk", None)
        chunk_id = getattr(chunk, "chunk_id", None)
        if chunk_id and str(chunk_id) in citation_text:
            covered += 1
    return _ratio(covered, len(retrieved))


def _average_metric(case_reports: list[dict[str, Any]], key: str) -> float | None:
    values = [case[key] for case in case_reports if case.get(key) is not None]
    if not values:
        return None
    return round(sum(float(value) for value in values) / len(values), 6)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


__all__ = [
    "AGENT4_EVALUATION_SCHEMA_VERSION",
    "DEFAULT_AGENT4_EVAL_SET_PATH",
    "DEFAULT_AGENT4_EVALUATION_REPORT_PATH",
    "Agent4EvalCase",
    "build_agent4_evaluation_report",
    "evaluate_agent4_case_state",
    "load_agent4_eval_cases",
    "run_agent4_evaluation",
]
