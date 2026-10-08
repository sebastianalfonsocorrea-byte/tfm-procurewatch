from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEMO_CONTRACT_KEY = "PW-2024-0001"
DEMO_QUESTION = "evidencia documental y riesgos explicables"
DEMO_OUTPUT_DIR = Path("data/processed/agent3_agent4_demo_2026_06_23")
DEMO_CORPUS_INDEX = Path("data/synthetic/agent4_corpus/agent4_corpus_index.json")
DEMO_CANONICAL_FILENAME = "agent2_contracts_canonical_demo.parquet"
DEMO_CASE_CONTEXT_FILENAME = "agent4_case_context_integrated_demo.json"
DEMO_REPORT_FILENAME = "agent2_agent3_agent4_demo_report.json"
DEMO_SOURCE_SNAPSHOT_ID = "demo_agent2_agent3_agent4_2026_06_24"
DEMO_SCHEMA_VERSION = "agent2_agent3_agent4_demo_report_v1"

DEMO_LIMITATIONS = [
    "Demo sintetica y offline: no usa raw completos ni descarga datos en vivo.",
    "No requiere Docker, PostgreSQL, Neo4j, Qdrant ni Ollama.",
    "Agent4 usa corpus documental local/sintetico y no declara fraude.",
]


def demo_contract_records(
    *,
    source_snapshot_id: str = DEMO_SOURCE_SNAPSHOT_ID,
) -> list[dict[str, object]]:
    return [
        {
            "contract_key_canon": "PW-2024-0001",
            "source": "synthetic",
            "source_record_id": "SYN-DEMO-0001",
            "source_dataset": "agent3_agent4_demo",
            "source_snapshot_id": source_snapshot_id,
            "buyer_name": "Ayuntamiento Demo Alfa",
            "buyer_id": "BUYER-DEMO-ALFA",
            "supplier_name": "Proveedor Demo Recurrente",
            "supplier_id": "SUP-DEMO-REC",
            "contract_title": "Servicios tecnicos de supervision de obra",
            "procedure": "negociado sin publicidad",
            "publication_date": "2024-03-01",
            "award_date": "2024-04-10",
            "estimated_value_eur": 100000.0,
            "awarded_value_eur": 125000.0,
            "cpv_codes_raw": "71000000-8;71200000-0",
            "cpv_code_list": "71000000;71200000",
            "source_file": "agent3_agent4_demo.parquet",
        },
        {
            "contract_key_canon": "PW-2024-0002",
            "source": "synthetic",
            "source_record_id": "SYN-DEMO-0002",
            "source_dataset": "agent3_agent4_demo",
            "source_snapshot_id": source_snapshot_id,
            "buyer_name": "Ayuntamiento Demo Alfa",
            "buyer_id": "BUYER-DEMO-ALFA",
            "supplier_name": "Proveedor Demo Recurrente",
            "supplier_id": "SUP-DEMO-REC",
            "contract_title": "Asistencia tecnica complementaria",
            "procedure": "abierto",
            "publication_date": "2024-05-01",
            "award_date": "2024-06-10",
            "estimated_value_eur": 80000.0,
            "awarded_value_eur": 78000.0,
            "cpv_codes_raw": "71000000-8",
            "cpv_code_list": "71000000",
            "source_file": "agent3_agent4_demo.parquet",
        },
        {
            "contract_key_canon": "PW-2024-0003",
            "source": "synthetic",
            "source_record_id": "SYN-DEMO-0003",
            "source_dataset": "agent3_agent4_demo",
            "source_snapshot_id": source_snapshot_id,
            "buyer_name": "Consorcio Demo Beta",
            "buyer_id": "BUYER-DEMO-BETA",
            "supplier_name": "Proveedor Demo Alternativo",
            "supplier_id": "SUP-DEMO-ALT",
            "contract_title": "Redaccion de proyecto tecnico",
            "procedure": "abierto",
            "publication_date": "2024-07-01",
            "award_date": "2024-08-10",
            "estimated_value_eur": 60000.0,
            "awarded_value_eur": 59000.0,
            "cpv_codes_raw": "71300000-1",
            "cpv_code_list": "71300000",
            "source_file": "agent3_agent4_demo.parquet",
        },
    ]


def write_demo_canonical(
    output_dir: Path = DEMO_OUTPUT_DIR,
    *,
    source_snapshot_id: str = DEMO_SOURCE_SNAPSHOT_ID,
) -> Path:
    import pandas as pd

    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = output_dir / DEMO_CANONICAL_FILENAME
    pd.DataFrame(demo_contract_records(source_snapshot_id=source_snapshot_id)).to_parquet(
        canonical_path,
        index=False,
    )
    return canonical_path


def run_integrated_demo(
    *,
    output_dir: Path = DEMO_OUTPUT_DIR,
    contract_key_canon: str = DEMO_CONTRACT_KEY,
    question: str = DEMO_QUESTION,
    corpus_index: Path = DEMO_CORPUS_INDEX,
) -> dict[str, Any]:
    from .agent3 import run_agent3
    from .agent4 import run_agent4_case_context

    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = write_demo_canonical(output_dir)
    agent3_report = run_agent3(input_path=canonical_path, output_dir=output_dir)
    case_context_path = output_dir / DEMO_CASE_CONTEXT_FILENAME
    state = run_agent4_case_context(
        contract_key_canon=contract_key_canon,
        question=question,
        canonical_path=canonical_path,
        agent3_features_path=output_dir / "agent3_agent2_features.parquet",
        corpus_index=corpus_index,
        output_path=case_context_path,
    )
    report = build_integrated_demo_report(
        output_dir=output_dir,
        contract_key_canon=contract_key_canon,
        question=question,
        corpus_index=corpus_index,
        canonical_path=canonical_path,
        agent3_report=agent3_report,
        agent4_state=state,
        case_context_path=case_context_path,
    )
    report_path = output_dir / DEMO_REPORT_FILENAME
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def build_integrated_demo_report(
    *,
    output_dir: Path,
    contract_key_canon: str,
    question: str,
    corpus_index: Path,
    canonical_path: Path,
    agent3_report: dict[str, Any],
    agent4_state: dict[str, Any],
    case_context_path: Path,
) -> dict[str, Any]:
    validations = _build_validations(
        output_dir=output_dir,
        canonical_path=canonical_path,
        agent3_report=agent3_report,
        agent4_state=agent4_state,
        case_context_path=case_context_path,
    )
    return {
        "schema_version": DEMO_SCHEMA_VERSION,
        "status": "ready" if all(item["passed"] for item in validations) else "failed",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "demo_type": "synthetic_offline",
        "contract_key_canon": contract_key_canon,
        "question": question,
        "source_snapshot_id": DEMO_SOURCE_SNAPSHOT_ID,
        "output_dir": str(output_dir),
        "corpus_index": str(corpus_index),
        "artifacts": {
            "canonical": str(canonical_path),
            "agent3_report": str(output_dir / "agent3_graph_report.json"),
            "agent3_nodes": str(output_dir / "agent3_nodes.parquet"),
            "agent3_edges": str(output_dir / "agent3_edges.parquet"),
            "agent3_features": str(output_dir / "agent3_agent2_features.parquet"),
            "agent4_case_context": str(case_context_path),
            "integrated_report": str(output_dir / DEMO_REPORT_FILENAME),
        },
        "summary": {
            "canonical_rows": int(agent3_report.get("input_rows", 0)),
            "agent3_nodes": int(agent3_report.get("nodes_rows", 0)),
            "agent3_edges": int(agent3_report.get("edges_rows", 0)),
            "agent3_communities": int(agent3_report.get("community_count", 0)),
            "agent3_features": int(agent3_report.get("agent2_features_rows", 0)),
            "agent2_risk_score": _agent2_risk_score(agent4_state),
            "agent2_red_flags": _agent2_red_flags(agent4_state),
            "agent4_evidences": len(_case_context(agent4_state).get("evidences", [])),
            "agent4_citations": len(_case_context(agent4_state).get("citations", [])),
            "agent4_warnings": len(agent4_state.get("warnings", [])),
        },
        "validations": validations,
        "limitations": DEMO_LIMITATIONS,
    }


def _build_validations(
    *,
    output_dir: Path,
    canonical_path: Path,
    agent3_report: dict[str, Any],
    agent4_state: dict[str, Any],
    case_context_path: Path,
) -> list[dict[str, object]]:
    case_context = _case_context(agent4_state)
    validations = [
        _validation("canonical_exists", canonical_path.exists(), str(canonical_path)),
        _validation(
            "agent3_outputs_exist",
            all((output_dir / filename).exists() for filename in _agent3_required_outputs()),
            "Agent3 report, parquet outputs and network summary exist.",
        ),
        _validation(
            "agent3_has_graph",
            int(agent3_report.get("nodes_rows", 0)) > 0
            and int(agent3_report.get("edges_rows", 0)) > 0,
            "Agent3 produced nodes and edges.",
        ),
        _validation(
            "agent3_has_communities_and_features",
            int(agent3_report.get("community_count", 0)) > 0
            and int(agent3_report.get("agent2_features_rows", 0)) > 0,
            "Agent3 produced communities and Agent2 features.",
        ),
        _validation(
            "agent4_case_context_exists",
            case_context_path.exists(),
            str(case_context_path),
        ),
        _validation(
            "agent4_has_agent2_score",
            bool(_agent2_red_flags(agent4_state)) and _agent2_risk_score(agent4_state) is not None,
            "Agent4 includes Agent2 risk score and red flags.",
        ),
        _validation(
            "agent4_has_agent3_metrics",
            bool(case_context.get("agent3_metrics_used")),
            "Agent4 includes Agent3 metrics.",
        ),
        _validation(
            "agent4_has_evidence_and_citations",
            bool(case_context.get("evidences")) and bool(case_context.get("citations")),
            "Agent4 includes evidences and citations.",
        ),
        _validation(
            "agent4_has_boundaries_and_scope",
            bool(case_context.get("decision_boundary")) and bool(case_context.get("agent4_scope")),
            "Agent4 includes decision boundary and MVP scope.",
        ),
    ]
    return validations


def _agent3_required_outputs() -> tuple[str, ...]:
    return (
        "agent3_graph_report.json",
        "agent3_nodes.parquet",
        "agent3_edges.parquet",
        "agent3_communities.parquet",
        "agent3_agent2_features.parquet",
        "agent3_network_summary.json",
    )


def _validation(name: str, passed: bool, details: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "details": details}


def _case_context(agent4_state: dict[str, Any]) -> dict[str, Any]:
    value = agent4_state.get("case_context")
    return value if isinstance(value, dict) else {}


def _agent2_risk_score(agent4_state: dict[str, Any]) -> float | None:
    score = agent4_state.get("agent2_score")
    if not isinstance(score, dict) or score.get("risk_score") is None:
        return None
    return float(score["risk_score"])


def _agent2_red_flags(agent4_state: dict[str, Any]) -> list[str]:
    score = agent4_state.get("agent2_score")
    if not isinstance(score, dict):
        return []
    flags = score.get("red_flags", [])
    return [str(flag) for flag in flags] if isinstance(flags, list) else []


__all__ = [
    "DEMO_CANONICAL_FILENAME",
    "DEMO_CONTRACT_KEY",
    "DEMO_CORPUS_INDEX",
    "DEMO_OUTPUT_DIR",
    "DEMO_QUESTION",
    "DEMO_REPORT_FILENAME",
    "DEMO_SCHEMA_VERSION",
    "DEMO_SOURCE_SNAPSHOT_ID",
    "build_integrated_demo_report",
    "demo_contract_records",
    "run_integrated_demo",
    "write_demo_canonical",
]
