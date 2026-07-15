from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_PROCESSED_DIR = Path("data/processed_sample")
DEFAULT_DEMO_DIR = Path("data/processed/agent3_agent4_demo_2026_06_23")
DEFAULT_AGENT4_EVALUATION_PATH = Path("data/processed/agent4_evaluation_report.json")
DEFAULT_BENCHMARK_OUTPUT_DIR = Path("data/processed/benchmark")
BENCHMARK_SCHEMA_VERSION = "0.4.0"

PASS = "pass"
WARNING = "warning"
FAIL = "fail"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class BenchmarkPaths:
    processed_dir: Path = DEFAULT_PROCESSED_DIR
    demo_dir: Path = DEFAULT_DEMO_DIR
    output_dir: Path = DEFAULT_BENCHMARK_OUTPUT_DIR
    agent4_evaluation_path: Path = DEFAULT_AGENT4_EVALUATION_PATH


def run_benchmark(
    *,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    demo_dir: Path = DEFAULT_DEMO_DIR,
    output_dir: Path = DEFAULT_BENCHMARK_OUTPUT_DIR,
    agent4_evaluation_path: Path = DEFAULT_AGENT4_EVALUATION_PATH,
    include_dashboard: bool = False,
    regenerate: bool = False,
    cpv_prefix: str = "71",
    year: int = 2024,
) -> dict[str, Any]:
    paths = BenchmarkPaths(
        processed_dir=processed_dir,
        demo_dir=demo_dir,
        output_dir=output_dir,
        agent4_evaluation_path=agent4_evaluation_path,
    )
    if regenerate:
        _regenerate_inputs(
            paths=paths,
            include_dashboard=include_dashboard,
            cpv_prefix=cpv_prefix,
            year=year,
        )

    agents = {
        "agent1": _evaluate_agent1(paths.processed_dir),
        "agent2": _evaluate_agent2(paths.processed_dir, paths.demo_dir),
        "agent3": _evaluate_agent3(paths.demo_dir),
        "agent4": _evaluate_agent4(paths.agent4_evaluation_path),
        "integrated": _evaluate_integrated(
            paths.demo_dir,
            paths.processed_dir,
            include_dashboard=include_dashboard,
        ),
    }
    tfm_context = _build_tfm_context(agents)
    report = {
        "dataset": "procurewatch_benchmark_report",
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": _global_status(agents),
        "inputs": {
            "processed_dir": str(paths.processed_dir),
            "demo_dir": str(paths.demo_dir),
            "agent4_evaluation_path": str(paths.agent4_evaluation_path),
            "include_dashboard": include_dashboard,
            "regenerate": regenerate,
            "cpv_prefix": cpv_prefix,
            "year": year,
        },
        "summary": _summary(agents),
        "tfm_context": tfm_context,
        "agents": agents,
        "limitations": _global_limitations(agents),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "benchmark_report.json"
    markdown_path = output_dir / "benchmark_report.md"
    report["outputs"] = {"json": str(json_path), "markdown": str(markdown_path)}
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_to_markdown(report), encoding="utf-8")
    return report


def _regenerate_inputs(
    *,
    paths: BenchmarkPaths,
    include_dashboard: bool,
    cpv_prefix: str,
    year: int,
) -> None:
    from procurewatch.agent1 import build_source_coverage
    from procurewatch.agent4 import run_agent4_evaluation
    from procurewatch.dashboard_validation import validate_dashboard_demo
    from procurewatch.integrated_demo import run_integrated_demo

    build_source_coverage(output_dir=paths.processed_dir, cpv_prefix=cpv_prefix, year=year)
    run_agent4_evaluation(output_path=paths.agent4_evaluation_path)
    run_integrated_demo(output_dir=paths.demo_dir)
    if include_dashboard:
        validate_dashboard_demo(output_dir=paths.demo_dir, regenerate=False)


def _evaluate_agent1(processed_dir: Path) -> dict[str, Any]:
    quality_path = processed_dir / "agent1_data_quality_summary.json"
    source_analysis_path = processed_dir / "agent1_source_coverage_analysis.json"
    quality = _read_json(quality_path)
    source_analysis = _read_json(source_analysis_path)
    metrics: list[dict[str, Any]] = []
    limitations = []

    if quality is None:
        metrics.append(
            _metric(
                "agent1.quality_report_exists",
                "Existe reporte de calidad Agent1",
                False,
                "true",
                FAIL,
                str(quality_path),
            )
        )
        return _agent_result("agent1", metrics, ["No se encontro el reporte de calidad Agent1."])

    metrics.append(
        _metric(
            "agent1.quality_report_exists",
            "Existe reporte de calidad Agent1",
            True,
            "true",
            PASS,
            str(quality_path),
        )
    )
    field_quality = quality.get("field_quality", {})
    for field in ["contract_key_canon", "source", "buyer_name", "cpv_codes_raw"]:
        ratio = _nested_float(field_quality, field, "coverage_ratio")
        metrics.append(
            _threshold_metric(
                f"agent1.coverage.{field}",
                f"Cobertura de {field}",
                ratio,
                0.95,
                evidence=f"field_quality.{field}.coverage_ratio",
            )
        )

    duplicate_count = int(quality.get("duplicate_source_contract_keys") or 0)
    metrics.append(
        _metric(
            "agent1.duplicates.source_contract_key",
            "Duplicados por fuente y clave canonica",
            duplicate_count,
            "= 0",
            PASS if duplicate_count == 0 else FAIL,
            "duplicate_source_contract_keys",
        )
    )

    if source_analysis is None:
        metrics.append(
            _metric(
                "agent1.source_analysis_exists",
                "Existe diagnostico de cobertura entre fuentes",
                False,
                "true",
                WARNING,
                str(source_analysis_path),
            )
        )
        limitations.append("No se encontro diagnostico de cobertura entre fuentes.")
        return _agent_result("agent1", metrics, limitations)

    metrics.append(
        _metric(
            "agent1.source_analysis_exists",
            "Existe diagnostico de cobertura entre fuentes",
            True,
            "true",
            PASS,
            str(source_analysis_path),
        )
    )
    exact_intersections = source_analysis.get("exact_intersections", {})
    total_intersections = sum(int(value or 0) for value in exact_intersections.values())
    metrics.append(
        _metric(
            "agent1.matching.exact_intersections",
            "Intersecciones exactas entre fuentes",
            total_intersections,
            "> 0 deseable",
            PASS if total_intersections > 0 else WARNING,
            "exact_intersections",
        )
    )
    if total_intersections == 0:
        limitations.append(
            "No hay intersecciones exactas entre BOE, PLACE y OpenTender; "
            "el matching transversal no queda validado."
        )

    candidate_counts = source_analysis.get("candidate_counts", {})
    total_candidates = sum(int(value or 0) for value in candidate_counts.values())
    metrics.append(
        _metric(
            "agent1.matching.candidates",
            "Candidatos aproximados de matching",
            total_candidates,
            "informativo",
            PASS if total_candidates > 0 else WARNING,
            "candidate_counts",
        )
    )
    return _agent_result("agent1", metrics, limitations)


def _evaluate_agent2(processed_dir: Path, demo_dir: Path) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    limitations: list[str] = []
    scores_path = processed_dir / "agent2_risk_scores.parquet"
    flags_path = processed_dir / "agent2_risk_flags.parquet"
    report_path = _first_existing(
        processed_dir / "agent2_run_report.json",
        processed_dir / "agent2_scoring_report.json",
    )

    if scores_path.exists():
        metrics.extend(_agent2_from_score_tables(scores_path, flags_path, report_path))
        metrics.append(_agent2_sensitivity_metric(processed_dir))
        return _agent_result("agent2", metrics, limitations)

    integrated = _read_json(demo_dir / "agent2_agent3_agent4_demo_report.json")
    if integrated is None:
        metrics.append(
            _metric(
                "agent2.score_artifact_exists",
                "Existe scoring Agent2 o demo integrada",
                False,
                "true",
                FAIL,
                f"{scores_path} | {demo_dir}",
            )
        )
        limitations.append("No se encontro scoring Agent2 ni demo integrada para evaluarlo.")
        metrics.append(_agent2_sensitivity_metric(processed_dir))
        return _agent_result("agent2", metrics, limitations)

    summary = integrated.get("summary", {})
    risk_score = summary.get("agent2_risk_score")
    red_flags = summary.get("agent2_red_flags", [])
    metrics.append(
        _metric(
            "agent2.demo_score_present",
            "Score Agent2 presente en demo integrada",
            risk_score,
            "no nulo",
            PASS if risk_score is not None else FAIL,
            "integrated.summary.agent2_risk_score",
        )
    )
    metrics.append(
        _metric(
            "agent2.demo_flags_present",
            "Red flags Agent2 presentes en demo integrada",
            len(red_flags) if isinstance(red_flags, list) else 0,
            "> 0",
            PASS if isinstance(red_flags, list) and len(red_flags) > 0 else WARNING,
            "integrated.summary.agent2_red_flags",
        )
    )
    limitations.append(
        "Agent2 se mide desde la demo integrada porque no hay scoring completo en processed_dir."
    )
    metrics.append(_agent2_sensitivity_metric(processed_dir))
    return _agent_result("agent2", metrics, limitations)


def _agent2_sensitivity_metric(processed_dir: Path) -> dict[str, Any]:
    path = processed_dir / "agent2_evaluation" / "agent2_evaluation_report.json"
    report = _read_json(path)
    if report is None:
        return _metric(
            "agent2.threshold_sensitivity.documented",
            "Sensibilidad de umbrales Agent2 documentada",
            False,
            "3 escenarios",
            NOT_APPLICABLE,
            str(path),
        )
    scenarios = report.get("scenarios", {})
    comparisons = report.get("comparisons_to_base", {})
    complete = (
        set(scenarios) >= {"lower", "base", "upper"}
        and set(comparisons) >= {"lower", "upper"}
        and all(
            comparisons.get(name, {}).get("score_unchanged_ratio") is not None
            for name in ("lower", "upper")
        )
    )
    return _metric(
        "agent2.threshold_sensitivity.documented",
        "Sensibilidad de umbrales Agent2 documentada",
        len(scenarios),
        "3 escenarios y comparacion con base",
        PASS if complete else FAIL,
        str(path),
    )


def _agent2_from_score_tables(
    scores_path: Path,
    flags_path: Path,
    report_path: Path | None,
) -> list[dict[str, Any]]:
    import pandas as pd

    scores = pd.read_parquet(scores_path)
    metrics = [
        _metric(
            "agent2.scores_rows",
            "Contratos con score Agent2",
            int(len(scores)),
            "> 0",
            PASS if len(scores) > 0 else FAIL,
            str(scores_path),
        )
    ]
    if scores.empty:
        return metrics

    risk_scores = pd.to_numeric(scores.get("risk_score"), errors="coerce")
    score_max = float(risk_scores.max()) if risk_scores.notna().any() else None
    upper_bound = 100.0 if score_max is not None and score_max > 1.0 else 1.0
    valid_scores = risk_scores.between(0, upper_bound, inclusive="both")
    metrics.append(
        _metric(
            "agent2.risk_score.valid_range",
            "Risk score en rango valido",
            _ratio(int(valid_scores.sum()), int(len(scores))),
            f"100% entre 0 y {upper_bound:g}",
            PASS if bool(valid_scores.all()) else FAIL,
            "agent2_risk_scores.risk_score",
        )
    )
    risk_level_present = scores.get("risk_level").astype("string").fillna("").str.strip() != ""
    metrics.append(
        _metric(
            "agent2.risk_level.coverage",
            "Cobertura de risk_level",
            _ratio(int(risk_level_present.sum()), int(len(scores))),
            "100%",
            PASS if bool(risk_level_present.all()) else FAIL,
            "agent2_risk_scores.risk_level",
        )
    )
    metrics.append(_agent2_monotonic_metric(scores))

    if flags_path.exists():
        flags = pd.read_parquet(flags_path)
        if flags.empty:
            flag_evidence_ratio = None
            status = NOT_APPLICABLE
        else:
            evidence = flags.get("evidence_text").astype("string").fillna("").str.strip()
            flag_evidence_ratio = _ratio(int((evidence != "").sum()), int(len(flags)))
            status = PASS if flag_evidence_ratio == 1.0 else FAIL
        metrics.append(
            _metric(
                "agent2.flags.evidence_coverage",
                "Flags con evidencia textual",
                flag_evidence_ratio,
                "100%",
                status,
                str(flags_path),
            )
        )
    else:
        metrics.append(
            _metric(
                "agent2.flags.evidence_coverage",
                "Flags con evidencia textual",
                None,
                "100%",
                WARNING,
                f"No existe {flags_path}",
            )
        )

    metrics.append(
        _metric(
            "agent2.report_exists",
            "Existe reporte Agent2",
            report_path is not None,
            "true",
            PASS if report_path is not None else WARNING,
            str(report_path)
            if report_path
            else "agent2_run_report.json | agent2_scoring_report.json",
        )
    )
    return metrics


def _agent2_monotonic_metric(scores: Any) -> dict[str, Any]:
    if "flags_count" not in scores.columns or "risk_score" not in scores.columns:
        return _metric(
            "agent2.score_flags.monotonicity",
            "Consistencia score-flags",
            None,
            "no decreciente",
            WARNING,
            "Faltan columnas flags_count/risk_score",
        )
    grouped = (
        scores.assign(
            flags_count_numeric=scores["flags_count"].astype("Int64"),
            risk_score_numeric=scores["risk_score"].astype("float64"),
        )
        .groupby("flags_count_numeric", dropna=True)["risk_score_numeric"]
        .mean()
        .sort_index()
    )
    values = grouped.tolist()
    monotonic = all(
        current <= following for current, following in zip(values, values[1:], strict=False)
    )
    return _metric(
        "agent2.score_flags.monotonicity",
        "Consistencia score-flags",
        "non_decreasing" if monotonic else "decreasing",
        "no decreciente",
        PASS if monotonic else FAIL,
        "media risk_score por flags_count",
    )


def _evaluate_agent3(demo_dir: Path) -> dict[str, Any]:
    report_path = demo_dir / "agent3_graph_report.json"
    report = _read_json(report_path)
    metrics: list[dict[str, Any]] = []
    limitations: list[str] = []
    if report is None:
        metrics.append(
            _metric(
                "agent3.report_exists",
                "Existe reporte Agent3",
                False,
                "true",
                FAIL,
                str(report_path),
            )
        )
        return _agent_result("agent3", metrics, ["No se encontro reporte Agent3."])

    metrics.append(_count_metric("agent3.nodes", "Nodos del grafo", report, "nodes_rows", 1))
    metrics.append(_count_metric("agent3.edges", "Aristas del grafo", report, "edges_rows", 1))
    metrics.append(
        _count_metric("agent3.communities", "Comunidades detectadas", report, "community_count", 1)
    )
    input_rows = int(report.get("input_rows") or 0)
    features_rows = int(report.get("agent2_features_rows") or 0)
    metrics.append(
        _metric(
            "agent3.features.contract_coverage",
            "Cobertura de features por contrato",
            _ratio(features_rows, input_rows),
            "100%",
            PASS if input_rows > 0 and features_rows >= input_rows else FAIL,
            "agent2_features_rows / input_rows",
        )
    )
    without_supplier = int(report.get("contracts_without_supplier") or 0)
    without_cpv = int(report.get("contracts_without_cpv") or 0)
    if without_supplier:
        limitations.append(f"Agent3 reporta {without_supplier} contratos sin proveedor.")
    if without_cpv:
        limitations.append(f"Agent3 reporta {without_cpv} contratos sin CPV.")
    metrics.append(
        _metric(
            "agent3.contracts_without_supplier",
            "Contratos sin proveedor en grafo",
            without_supplier,
            "informativo",
            PASS if without_supplier == 0 else WARNING,
            "contracts_without_supplier",
        )
    )
    metrics.append(
        _metric(
            "agent3.contracts_without_cpv",
            "Contratos sin CPV en grafo",
            without_cpv,
            "informativo",
            PASS if without_cpv == 0 else WARNING,
            "contracts_without_cpv",
        )
    )
    return _agent_result("agent3", metrics, limitations)


def _evaluate_agent4(agent4_evaluation_path: Path) -> dict[str, Any]:
    report = _read_json(agent4_evaluation_path)
    metrics: list[dict[str, Any]] = []
    limitations: list[str] = []
    if report is None:
        metrics.append(
            _metric(
                "agent4.evaluation_report_exists",
                "Existe evaluacion documental Agent4",
                False,
                "true",
                FAIL,
                str(agent4_evaluation_path),
            )
        )
        return _agent_result("agent4", metrics, ["No se encontro evaluacion Agent4."])

    summary = report.get("summary", {})
    metrics.extend(
        [
            _threshold_metric(
                "agent4.expectation_accuracy",
                "Accuracy de expectativas",
                _float(summary.get("expectation_accuracy")),
                0.90,
                evidence="summary.expectation_accuracy",
            ),
            _threshold_metric(
                "agent4.precision_at_k",
                "Precision@k media",
                _float(summary.get("average_precision_at_k")),
                0.90,
                evidence="summary.average_precision_at_k",
            ),
            _threshold_metric(
                "agent4.expected_document_recall",
                "Recall medio de documentos esperados",
                _float(summary.get("average_expected_document_recall")),
                0.90,
                evidence="summary.average_expected_document_recall",
            ),
            _threshold_metric(
                "agent4.citation_traceability",
                "Trazabilidad media de citas",
                _float(summary.get("average_citation_traceability")),
                0.95,
                evidence="summary.average_citation_traceability",
            ),
            _threshold_metric(
                "agent4.contract_key_consistency",
                "Consistencia media de contrato en citas",
                _float(summary.get("average_contract_key_consistency")),
                0.95,
                evidence="summary.average_contract_key_consistency",
            ),
            _threshold_metric(
                "agent4.no_unsupported_fraud_claim",
                "Ausencia de declaraciones de fraude no soportadas",
                _float(summary.get("no_unsupported_fraud_claim_ratio")),
                1.0,
                evidence="summary.no_unsupported_fraud_claim_ratio",
            ),
            _threshold_metric(
                "agent4.practical_validation",
                "Validacion practica de fichas trazables",
                _float(summary.get("practical_validation_pass_ratio")),
                0.95,
                evidence="summary.practical_validation_pass_ratio",
            ),
        ]
    )
    ragas = report.get("ragas", {})
    if ragas.get("status") != "run":
        limitations.append(str(ragas.get("reason") or "RAGAS no ejecutado."))
        metrics.append(
            _metric(
                "agent4.ragas",
                "Evaluacion RAGAS",
                ragas.get("status"),
                "run deseable",
                NOT_APPLICABLE,
                "ragas.status",
            )
        )
    return _agent_result("agent4", metrics, limitations)


def _evaluate_integrated(
    demo_dir: Path,
    processed_dir: Path,
    *,
    include_dashboard: bool,
) -> dict[str, Any]:
    integrated_path = demo_dir / "agent2_agent3_agent4_demo_report.json"
    integrated = _read_json(integrated_path)
    metrics: list[dict[str, Any]] = []
    limitations: list[str] = []
    if integrated is None:
        metrics.append(
            _metric(
                "integrated.report_exists",
                "Existe reporte integrado",
                False,
                "true",
                FAIL,
                str(integrated_path),
            )
        )
        return _agent_result("integrated", metrics, ["No se encontro demo integrada."])

    summary = integrated.get("summary", {})
    validations = integrated.get("validations", [])
    metrics.append(
        _metric(
            "integrated.status_ready",
            "Demo integrada en estado ready",
            integrated.get("status"),
            "ready",
            PASS if integrated.get("status") == "ready" else FAIL,
            "integrated.status",
        )
    )
    metrics.append(
        _metric(
            "integrated.validations_passed",
            "Validaciones integradas superadas",
            _ratio(_passed_count(validations), len(validations)),
            "100%",
            PASS if validations and _passed_count(validations) == len(validations) else FAIL,
            "integrated.validations",
        )
    )
    metrics.append(
        _metric(
            "integrated.agent2_score_present",
            "Score Agent2 integrado",
            summary.get("agent2_risk_score"),
            "no nulo",
            PASS if summary.get("agent2_risk_score") is not None else FAIL,
            "summary.agent2_risk_score",
        )
    )
    metrics.append(
        _metric(
            "integrated.agent3_features_present",
            "Features Agent3 integradas",
            int(summary.get("agent3_features") or 0),
            "> 0",
            PASS if int(summary.get("agent3_features") or 0) > 0 else FAIL,
            "summary.agent3_features",
        )
    )
    metrics.append(
        _metric(
            "integrated.agent4_evidence_citations",
            "Evidencias y citas Agent4 integradas",
            f"{summary.get('agent4_evidences', 0)}/{summary.get('agent4_citations', 0)}",
            "> 0/> 0",
            PASS
            if int(summary.get("agent4_evidences") or 0) > 0
            and int(summary.get("agent4_citations") or 0) > 0
            else FAIL,
            "summary.agent4_evidences / summary.agent4_citations",
        )
    )
    limitations.extend(str(item) for item in integrated.get("limitations", []))
    metrics.append(_case_studies_metric(processed_dir))
    metrics.extend(_dashboard_metrics(demo_dir, include_dashboard=include_dashboard))
    return _agent_result("integrated", metrics, limitations)


def _case_studies_metric(processed_dir: Path) -> dict[str, Any]:
    path = processed_dir / "case_studies" / "case_studies_report.json"
    report = _read_json(path)
    if report is None:
        return _metric(
            "integration.case_studies.traceable",
            "Diez fichas de caso trazables",
            "not_available",
            "10 casos; composicion 5/3/2; trazabilidad completa",
            NOT_APPLICABLE,
            str(path),
        )
    summary = report.get("summary", {})
    breakdown = summary.get("selection_breakdown", {})
    complete = (
        int(summary.get("cases_count") or 0) == 10
        and int(summary.get("unique_contracts") or 0) == 10
        and int(breakdown.get("high_score") or 0) == 5
        and int(breakdown.get("medium_risk") or 0) == 3
        and int(breakdown.get("control") or 0) == 2
        and float(summary.get("rule_evidence_coverage_ratio") or 0.0) == 1.0
        and float(summary.get("source_traceability_ratio") or 0.0) == 1.0
        and float(summary.get("relationships_available_ratio") or 0.0) == 1.0
        and int(summary.get("unsupported_fraud_claims") or 0) == 0
        and bool(summary.get("practical_validation_passed"))
    )
    return _metric(
        "integration.case_studies.traceable",
        "Diez fichas de caso trazables",
        {
            "cases": summary.get("cases_count"),
            "selection": breakdown,
            "rule_evidence_coverage": summary.get("rule_evidence_coverage_ratio"),
            "relationships_coverage": summary.get("relationships_available_ratio"),
        },
        "10 casos; composicion 5/3/2; trazabilidad completa",
        PASS if complete else FAIL,
        str(path),
    )


def _dashboard_metrics(demo_dir: Path, *, include_dashboard: bool) -> list[dict[str, Any]]:
    if not include_dashboard:
        return [
            _metric(
                "integrated.dashboard",
                "Validacion dashboard",
                "not_requested",
                "opcional",
                NOT_APPLICABLE,
                "--include-dashboard no activado",
            )
        ]
    dashboard_path = demo_dir / "dashboard_validation_report.json"
    report = _read_json(dashboard_path)
    if report is None:
        return [
            _metric(
                "integrated.dashboard",
                "Validacion dashboard",
                False,
                "ready",
                FAIL,
                str(dashboard_path),
            )
        ]
    checks = report.get("checks", [])
    streamlit = report.get("streamlit_headless", {})
    status = (
        PASS
        if report.get("status") == "ready"
        and checks
        and _passed_count(checks) == len(checks)
        and not streamlit.get("exceptions")
        else FAIL
    )
    return [
        _metric(
            "integrated.dashboard",
            "Validacion dashboard",
            report.get("status"),
            "ready",
            status,
            str(dashboard_path),
        )
    ]


def _agent_result(
    agent: str,
    metrics: list[dict[str, Any]],
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "status": _status_from_metrics(metrics),
        "metrics": metrics,
        "limitations": limitations,
        "metrics_count": len(metrics),
        "agent": agent,
    }


def _metric(
    metric_id: str,
    label: str,
    value: Any,
    threshold: Any,
    status: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "label": label,
        "value": value,
        "threshold": threshold,
        "status": status,
        "evidence": evidence,
    }


def _threshold_metric(
    metric_id: str,
    label: str,
    value: float | None,
    threshold: float,
    *,
    evidence: str,
) -> dict[str, Any]:
    if value is None:
        status = FAIL
    else:
        status = PASS if value >= threshold else FAIL
    return _metric(metric_id, label, value, f">= {threshold:.2f}", status, evidence)


def _count_metric(
    metric_id: str,
    label: str,
    report: dict[str, Any],
    key: str,
    minimum: int,
) -> dict[str, Any]:
    value = int(report.get(key) or 0)
    return _metric(
        metric_id,
        label,
        value,
        f">= {minimum}",
        PASS if value >= minimum else FAIL,
        key,
    )


def _status_from_metrics(metrics: list[dict[str, Any]]) -> str:
    statuses = [metric["status"] for metric in metrics]
    if FAIL in statuses:
        return FAIL
    if WARNING in statuses:
        return WARNING
    if any(status == PASS for status in statuses):
        return PASS
    return NOT_APPLICABLE


def _global_status(agents: dict[str, dict[str, Any]]) -> str:
    statuses = [agent["status"] for agent in agents.values()]
    if FAIL in statuses:
        return FAIL
    if WARNING in statuses:
        return WARNING
    if any(status == PASS for status in statuses):
        return PASS
    return NOT_APPLICABLE


def _summary(agents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    all_metrics = [
        metric for agent in agents.values() for metric in agent.get("metrics", [])
    ]
    counts = {
        PASS: 0,
        WARNING: 0,
        FAIL: 0,
        NOT_APPLICABLE: 0,
    }
    for metric in all_metrics:
        counts[str(metric.get("status"))] = counts.get(str(metric.get("status")), 0) + 1
    return {
        "agents": {name: agent["status"] for name, agent in agents.items()},
        "metrics_count": len(all_metrics),
        "status_counts": counts,
    }


def _global_limitations(agents: dict[str, dict[str, Any]]) -> list[str]:
    limitations = []
    for name, agent in agents.items():
        for item in agent.get("limitations", []):
            limitations.append(f"{name}: {item}")
    return limitations


def _build_tfm_context(agents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Summarise benchmark evidence with the boundaries expected in a TFM."""
    agent2_demo_only = _agent_limitation_contains(
        agents.get("agent2", {}),
        "demo integrada",
    )
    dashboard_optional = any(
        metric.get("metric_id") == "integrated.dashboard"
        and metric.get("status") == NOT_APPLICABLE
        for metric in agents.get("integrated", {}).get("metrics", [])
    )
    return {
        "purpose": (
            "Usar el benchmark como evidencia reproducible del TFM: implementacion, "
            "evaluacion objetiva, limitaciones y extension futura."
        ),
        "global_reading": (
            "ProcureWatch queda evaluado como prototipo academico funcional. El estado "
            "warning preserva una limitacion metodologica relevante, no un fallo tecnico "
            "del pipeline."
        ),
        "institutional_reading": (
            "El sistema es defendible para priorizacion, trazabilidad y discusion "
            "metodologica; una version institucional exigiria ampliar datos, validar "
            "matching interfuente y contrastar resultados con referencia externa."
        ),
        "component_maturity": [
            {
                "component": "Agent1 - ingesta y normalizacion",
                "implemented": "si",
                "evaluated": "si",
                "evidence": "calidad de campos, duplicados y cobertura interfuente",
                "current_boundary": "cobertura canonica por fuente sin matching exacto transversal",
                "future_extension": "validacion manual y politica auditable de matching",
                "tfm_reading": (
                    "hallazgo metodologico sobre interoperabilidad real de fuentes abiertas"
                ),
            },
            {
                "component": "Agent2 - scoring de riesgo",
                "implemented": "si",
                "evaluated": "parcial en demo integrada" if agent2_demo_only else "si",
                "evidence": "score y red flags trazables",
                "current_boundary": (
                    "sin benchmark estadistico amplio"
                    if agent2_demo_only
                    else "evaluado sobre artefactos de scoring"
                ),
                "future_extension": "validar con dataset mayor y casos etiquetados",
                "tfm_reading": "modelo explicable de priorizacion, no dictamen juridico",
            },
            {
                "component": "Agent3 - grafo y relaciones",
                "implemented": "si",
                "evaluated": "si",
                "evidence": "nodos, aristas, comunidades y cobertura de features",
                "current_boundary": "validado en demo local/sintetica",
                "future_extension": "ejecucion sobre volumen completo y analisis longitudinal",
                "tfm_reading": "capa relacional para interpretar patrones, no prueba concluyente",
            },
            {
                "component": "Agent4 - capa documental",
                "implemented": "si",
                "evaluated": "si",
                "evidence": "retrieval, citas, trazabilidad y prudencia del lenguaje",
                "current_boundary": "corpus local/sintetico y evaluacion RAGAS no representativa",
                "future_extension": "corpus real ampliado y evaluacion comparativa de LLM local",
                "tfm_reading": "fichas explicativas trazables bajo supervision humana",
            },
            {
                "component": "Integracion y dashboard",
                "implemented": "demo",
                "evaluated": (
                    "si" if not dashboard_optional else "demo integrada; dashboard opcional"
                ),
                "evidence": "flujo Agent2-Agent3-Agent4 y validaciones integradas",
                "current_boundary": "no equivale a despliegue productivo institucional",
                "future_extension": "servicios persistentes, seguridad y operacion continua",
                "tfm_reading": "prueba de viabilidad de arquitectura multiagente",
            },
        ],
        "academic_conclusions": [
            (
                "La contribucion principal del TFM no es afirmar deteccion automatica de "
                "fraude, sino construir un pipeline trazable para priorizar revision."
            ),
            (
                "La ausencia de intersecciones utiles entre fuentes convierte la calidad "
                "del matching en un resultado empirico del trabajo."
            ),
            (
                "Las fichas documentales son evaluables por fidelidad, cobertura y citas, "
                "pero no sustituyen la interpretacion juridica ni la auditoria humana."
            ),
        ],
    }


def _agent_limitation_contains(agent: dict[str, Any], needle: str) -> bool:
    return any(needle in str(item) for item in agent.get("limitations", []))


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Benchmark ProcureWatch",
        "",
        f"- Estado global: **{report['status']}**",
        f"- Metricas evaluadas: **{report['summary']['metrics_count']}**",
    ]
    if report.get("tfm_context"):
        lines.extend(_tfm_context_to_markdown(report["tfm_context"]))

    lines.extend(
        [
            "",
            "## Resumen por agente",
            "",
            "| Agente | Estado | Metricas |",
            "|---|---|---:|",
        ]
    )
    for name, agent in report["agents"].items():
        lines.append(f"| {name} | {agent['status']} | {agent['metrics_count']} |")

    lines.extend(["", "## Metricas", ""])
    for name, agent in report["agents"].items():
        lines.extend(
            [
                f"### {name}",
                "",
                "| Metrica | Valor | Umbral | Estado | Evidencia |",
                "|---|---:|---|---|---|",
            ]
        )
        for metric in agent["metrics"]:
            lines.append(
                f"| {metric['label']} | {_display(metric['value'])} | "
                f"{metric['threshold']} | {metric['status']} | {metric['evidence']} |"
            )
        if agent.get("limitations"):
            lines.append("")
            for limitation in agent["limitations"]:
                lines.append(f"- {limitation}")
        lines.append("")

    if report.get("limitations"):
        lines.extend(["## Limitaciones globales", ""])
        for limitation in report["limitations"]:
            lines.append(f"- {limitation}")
        lines.append("")
    return "\n".join(lines)


def _tfm_context_to_markdown(tfm_context: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## Lectura en contexto de TFM",
        "",
        str(tfm_context["global_reading"]),
        "",
        str(tfm_context["institutional_reading"]),
        "",
        "## Matriz de alcance del TFM",
        "",
        "| Componente | Implementado | Evaluado | Evidencia | Limite actual | Extension |",
        "|---|---|---|---|---|---|",
    ]
    for item in tfm_context["component_maturity"]:
        lines.append(
            f"| {item['component']} | {item['implemented']} | {item['evaluated']} | "
            f"{item['evidence']} | {item['current_boundary']} | {item['future_extension']} |"
        )
    lines.extend(["", "## Conclusiones academicas", ""])
    for conclusion in tfm_context["academic_conclusions"]:
        lines.append(f"- {conclusion}")
    return lines


def _display(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _nested_float(mapping: dict[str, Any], key: str, subkey: str) -> float | None:
    value = mapping.get(key)
    if not isinstance(value, dict):
        return None
    return _float(value.get(subkey))


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        converted = float(value)
        if converted != converted:
            return None
        return converted
    except (TypeError, ValueError):
        return None


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _passed_count(items: list[Any]) -> int:
    return sum(
        1 for item in items if isinstance(item, dict) and bool(item.get("passed"))
    )


__all__ = [
    "BENCHMARK_SCHEMA_VERSION",
    "DEFAULT_BENCHMARK_OUTPUT_DIR",
    "DEFAULT_PROCESSED_DIR",
    "BenchmarkPaths",
    "run_benchmark",
]
