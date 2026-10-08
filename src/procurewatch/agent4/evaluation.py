from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .corpus import DEFAULT_SYNTHETIC_CORPUS_INDEX
from .graph import run_agent4_case_flow
from .qdrant_store import DEFAULT_QDRANT_COLLECTION
from .source_registry import build_agent4_capabilities, build_agent4_source_registry_summary

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
    markdown_path = output_path.with_suffix(".md")
    report["outputs"] = {
        "json": str(output_path),
        "markdown": str(markdown_path),
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_to_markdown(report), encoding="utf-8")
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
    answer_text = str(state.get("answer") or "")
    case_context = state.get("case_context", {})
    case_context = case_context if isinstance(case_context, dict) else {}
    citation_traceability_ratio = _citation_traceability_coverage(
        retrieved,
        citations,
        case.contract_key_canon,
    )
    contract_key_consistency_ratio = _contract_key_consistency(
        retrieved,
        case.contract_key_canon,
    )
    decision_boundary_present = _decision_boundary_present(answer_text, case_context)
    no_evidence_warning_present = _no_evidence_warning_present(state)
    unsupported_fraud_claim = _has_unsupported_fraud_claim(answer_text, case_context)

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
        "citation_traceability_ratio": citation_traceability_ratio,
        "contract_key_consistency_ratio": contract_key_consistency_ratio,
        "decision_boundary_present": decision_boundary_present,
        "no_evidence_warning_present": no_evidence_warning_present,
        "unsupported_fraud_claim": unsupported_fraud_claim,
        "practical_validation_passed": _practical_validation_passed(
            has_evidence=has_evidence,
            expectation_met=has_evidence == case.expect_evidence,
            citation_traceability_ratio=citation_traceability_ratio,
            contract_key_consistency_ratio=contract_key_consistency_ratio,
            decision_boundary_present=decision_boundary_present,
            no_evidence_warning_present=no_evidence_warning_present,
            unsupported_fraud_claim=unsupported_fraud_claim,
        ),
        "generation_mode": _generation_mode(case_context),
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
    capabilities = build_agent4_capabilities()
    summary = {
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
        "average_citation_traceability": _average_metric(
            case_reports,
            "citation_traceability_ratio",
        ),
        "average_contract_key_consistency": _average_metric(
            case_reports,
            "contract_key_consistency_ratio",
        ),
        "decision_boundary_coverage": _boolean_ratio(
            case_reports,
            "decision_boundary_present",
        ),
        "no_unsupported_fraud_claim_ratio": _inverse_boolean_ratio(
            case_reports,
            "unsupported_fraud_claim",
        ),
        "practical_validation_pass_ratio": _boolean_ratio(
            case_reports,
            "practical_validation_passed",
        ),
        "warnings_count": total_warnings,
    }
    return {
        "dataset": "agent4_evaluation_report",
        "schema_version": AGENT4_EVALUATION_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "eval_set_path": str(eval_set_path),
        "corpus_index": str(corpus_index),
        "mode": "services" if use_services else "offline",
        "retrieval_limit": retrieval_limit,
        "agent4_scope": capabilities["scope"],
        "document_source_policy": capabilities["document_source_policy"],
        "implemented_in_mvp": capabilities["implemented_in_mvp"],
        "not_implemented_in_mvp": capabilities["not_implemented_in_mvp"],
        "official_source_registry": build_agent4_source_registry_summary(),
        "summary": summary,
        "tfm_practical_evaluation": _build_tfm_practical_evaluation(summary, use_services),
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


def _build_tfm_practical_evaluation(
    summary: dict[str, Any],
    use_services: bool,
) -> dict[str, Any]:
    llm_local_scope = (
        "La ejecucion con servicios permite usar Qdrant y Ollama/modelo local; la evaluacion "
        "mantiene la misma frontera: el LLM explica evidencia, no decide riesgo ni fraude."
        if use_services
        else (
            "La evaluacion offline valida recuperacion, citas y estructura de ficha. La calidad "
            "generativa del LLM local queda como contraste futuro con el mismo protocolo."
        )
    )
    return {
        "tfm_reading": (
            "La capa documental se evalua como soporte explicativo del TFM: debe recuperar "
            "evidencia, citarla de forma trazable, conservar el contrato correcto y evitar "
            "afirmaciones no soportadas."
        ),
        "llm_local_scope": llm_local_scope,
        "dimensions": [
            {
                "dimension": "Fidelidad documental",
                "metric": "average_precision_at_k",
                "value": summary.get("average_precision_at_k"),
                "reading": "la evidencia recuperada coincide con documentos esperados",
            },
            {
                "dimension": "Cobertura documental",
                "metric": "average_expected_document_recall",
                "value": summary.get("average_expected_document_recall"),
                "reading": "los documentos esperados aparecen en el contexto recuperado",
            },
            {
                "dimension": "Trazabilidad de citas",
                "metric": "average_citation_traceability",
                "value": summary.get("average_citation_traceability"),
                "reading": "las citas conservan document_id, chunk_id y contract_key_canon",
            },
            {
                "dimension": "Consistencia del contrato",
                "metric": "average_contract_key_consistency",
                "value": summary.get("average_contract_key_consistency"),
                "reading": "la evidencia usada pertenece al contrato consultado",
            },
            {
                "dimension": "Prudencia explicativa",
                "metric": "no_unsupported_fraud_claim_ratio",
                "value": summary.get("no_unsupported_fraud_claim_ratio"),
                "reading": "la ficha no declara fraude sin soporte documental",
            },
            {
                "dimension": "Validacion practica",
                "metric": "practical_validation_pass_ratio",
                "value": summary.get("practical_validation_pass_ratio"),
                "reading": "los casos cumplen las condiciones minimas de ficha trazable",
            },
        ],
        "validated_scope": [
            "retrieval local sobre corpus sintetico",
            "citas trazables por documento, fragmento y contrato",
            "casos con evidencia y caso negativo sin evidencia",
            "frontera de decision orientada a revision humana",
        ],
        "future_validation": [
            "ampliar corpus con pliegos y adjudicaciones reales heterogeneas",
            "comparar modo offline, Qdrant y LLM local con el mismo set de evaluacion",
            "incorporar mas casos negativos y preguntas adversariales",
            "ejecutar RAGAS u otra evaluacion externa cuando el corpus sea representativo",
        ],
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


def _citation_traceability_coverage(
    retrieved: list[object],
    citations: list[str],
    contract_key_canon: str,
) -> float | None:
    if not retrieved:
        return None
    citation_text = "\n".join(citations)
    covered = 0
    for result in retrieved:
        chunk = getattr(result, "chunk", None)
        document_id = getattr(chunk, "document_id", None)
        chunk_id = getattr(chunk, "chunk_id", None)
        chunk_contract_key = getattr(chunk, "contract_key_canon", None) or contract_key_canon
        if (
            document_id
            and chunk_id
            and str(document_id) in citation_text
            and str(chunk_id) in citation_text
            and f"contract_key_canon={chunk_contract_key}" in citation_text
        ):
            covered += 1
    return _ratio(covered, len(retrieved))


def _contract_key_consistency(
    retrieved: list[object],
    contract_key_canon: str,
) -> float | None:
    if not retrieved:
        return None
    consistent = 0
    for result in retrieved:
        chunk = getattr(result, "chunk", None)
        chunk_contract_key = getattr(chunk, "contract_key_canon", None)
        if chunk_contract_key == contract_key_canon:
            consistent += 1
    return _ratio(consistent, len(retrieved))


def _decision_boundary_present(answer_text: str, case_context: dict[str, Any]) -> bool:
    values = [
        answer_text,
        str(case_context.get("summary") or ""),
        str(case_context.get("decision_boundary") or ""),
    ]
    normalized = " ".join(values).lower()
    return "no se declara fraude" in normalized or "revision humana" in normalized


def _no_evidence_warning_present(state: dict[str, Any]) -> bool:
    warnings = " ".join(str(value) for value in state.get("warnings", [])).lower()
    return "no hay evidencia documental recuperada" in warnings


def _has_unsupported_fraud_claim(answer_text: str, case_context: dict[str, Any]) -> bool:
    values = [
        answer_text,
        str(case_context.get("summary") or ""),
        str(case_context.get("decision_boundary") or ""),
    ]
    normalized = " ".join(" ".join(values).lower().split())
    for safe_phrase in [
        "no se declara fraude",
        "no declara fraude",
        "no se ha declarado fraude",
    ]:
        normalized = normalized.replace(safe_phrase, "")
    risky_phrases = [
        "declara fraude",
        "fraude confirmado",
        "se ha detectado fraude",
        "contrato fraudulento",
    ]
    return any(phrase in normalized for phrase in risky_phrases)


def _practical_validation_passed(
    *,
    has_evidence: bool,
    expectation_met: bool,
    citation_traceability_ratio: float | None,
    contract_key_consistency_ratio: float | None,
    decision_boundary_present: bool,
    no_evidence_warning_present: bool,
    unsupported_fraud_claim: bool,
) -> bool:
    if not expectation_met or unsupported_fraud_claim or not decision_boundary_present:
        return False
    if has_evidence:
        return citation_traceability_ratio == 1.0 and contract_key_consistency_ratio == 1.0
    return no_evidence_warning_present


def _generation_mode(case_context: dict[str, Any]) -> str | None:
    generation = case_context.get("generation")
    if not isinstance(generation, dict):
        return None
    mode = generation.get("mode")
    return str(mode) if mode else None


def _average_metric(case_reports: list[dict[str, Any]], key: str) -> float | None:
    values = [case[key] for case in case_reports if case.get(key) is not None]
    if not values:
        return None
    return round(sum(float(value) for value in values) / len(values), 6)


def _boolean_ratio(case_reports: list[dict[str, Any]], key: str) -> float | None:
    if not case_reports:
        return None
    positives = sum(1 for case in case_reports if bool(case.get(key)))
    return _ratio(positives, len(case_reports))


def _inverse_boolean_ratio(case_reports: list[dict[str, Any]], key: str) -> float | None:
    if not case_reports:
        return None
    negatives = sum(1 for case in case_reports if not bool(case.get(key)))
    return _ratio(negatives, len(case_reports))


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _to_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    tfm_practical = report.get("tfm_practical_evaluation", {})
    lines = [
        "# Evaluacion documental Agent4",
        "",
        f"- Modo: **{report['mode']}**",
        f"- Casos: **{summary['cases_count']}**",
        f"- Casos con evidencia: **{summary['cases_with_evidence']}**",
        f"- Accuracy de expectativas: **{_format_ratio(summary['expectation_accuracy'])}**",
        f"- Precision@k media: **{_format_ratio(summary['average_precision_at_k'])}**",
        (
            "- Recall medio de documentos esperados: "
            f"**{_format_ratio(summary['average_expected_document_recall'])}**"
        ),
        f"- Cobertura media de citas: **{_format_ratio(summary['average_citation_coverage'])}**",
        (
            "- Trazabilidad media de citas: "
            f"**{_format_ratio(summary['average_citation_traceability'])}**"
        ),
        (
            "- Consistencia media de contrato: "
            f"**{_format_ratio(summary['average_contract_key_consistency'])}**"
        ),
        (
            "- Ratio de validacion practica: "
            f"**{_format_ratio(summary['practical_validation_pass_ratio'])}**"
        ),
    ]
    if tfm_practical:
        lines.extend(_tfm_practical_to_markdown(tfm_practical))

    lines.extend(
        [
            "",
            "## Casos",
            "",
            "| Caso | Evidencia | Citas | Precision@k | Recall docs | Validacion |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for case in report["cases"]:
        lines.append(
            f"| {case['case_id']} | {case['evidence_count']} | {case['citation_count']} | "
            f"{_format_ratio(case['precision_at_k'])} | "
            f"{_format_ratio(case['expected_document_recall'])} | "
            f"{'ok' if case['practical_validation_passed'] else 'review'} |"
        )

    lines.extend(["", "## Limites", ""])
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def _tfm_practical_to_markdown(tfm_practical: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## Evaluacion practica para el TFM",
        "",
        str(tfm_practical["tfm_reading"]),
        "",
        f"**LLM local:** {tfm_practical['llm_local_scope']}",
        "",
        "| Dimension | Metrica | Resultado | Lectura |",
        "|---|---|---:|---|",
    ]
    for item in tfm_practical["dimensions"]:
        lines.append(
            f"| {item['dimension']} | {item['metric']} | {_format_ratio(item['value'])} | "
            f"{item['reading']} |"
        )
    lines.extend(["", "### Alcance validado", ""])
    for item in tfm_practical["validated_scope"]:
        lines.append(f"- {item}")
    lines.extend(["", "### Futuras iteraciones", ""])
    for item in tfm_practical["future_validation"]:
        lines.append(f"- {item}")
    return lines


def _format_ratio(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"


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
