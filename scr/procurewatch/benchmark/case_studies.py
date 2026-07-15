from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CASE_STUDY_SCHEMA_VERSION = "1.0.0"
DEFAULT_CANONICAL_PATH = Path("data/processed_sample/agent2_contracts_canonical.parquet")
DEFAULT_SCORES_PATH = Path(
    "data/processed_sample/agent2_evaluation/base/agent2_risk_scores.parquet"
)
DEFAULT_FLAGS_PATH = Path(
    "data/processed_sample/agent2_evaluation/base/agent2_risk_flags.parquet"
)
DEFAULT_AGENT3_FEATURES_PATH = Path(
    "data/processed_sample/agent3_case_studies/agent3_agent2_features.parquet"
)
DEFAULT_CORPUS_INDEX_PATH = Path("data/synthetic/agent4_corpus/agent4_corpus_index.json")
DEFAULT_CASE_STUDIES_OUTPUT_DIR = Path("data/processed_sample/case_studies")

REQUIRED_CANONICAL_COLUMNS = {
    "contract_key_canon",
    "source",
    "source_record_id",
    "buyer_name",
    "supplier_name",
    "procedure",
    "estimated_value_eur",
    "awarded_value_eur",
}
REQUIRED_SCORE_COLUMNS = {
    "contract_key_canon",
    "risk_score",
    "risk_level",
    "flags_count",
    "top_flags",
    "evaluable_rules_count",
    "not_evaluable_rules",
    "evaluation_status",
}
REQUIRED_FLAG_COLUMNS = {
    "contract_key_canon",
    "flag_code",
    "evidence_fields",
    "evidence_text",
    "rule_version",
}
RELATIONSHIP_FIELDS = (
    "buyer_supplier_recurrence",
    "buyer_supplier_contract_share",
    "buyer_degree",
    "supplier_degree",
    "supplier_contracts_count",
    "contract_neighbor_count",
    "contract_degree_centrality",
    "contract_betweenness_centrality",
    "component_id",
    "component_size",
    "community_id",
    "community_size",
    "cpv_count",
    "has_supplier",
    "agent3_version",
)
CONTRACT_FIELDS = (
    "contract_key_canon",
    "source",
    "source_record_id",
    "source_dataset",
    "source_file",
    "buyer_name",
    "buyer_id",
    "supplier_name",
    "supplier_id",
    "contract_title",
    "procedure",
    "publication_date",
    "award_date",
    "estimated_value_eur",
    "awarded_value_eur",
    "cpv_codes_raw",
    "cpv_code_list",
)
IMPORTANT_FIELDS = (
    "source",
    "source_record_id",
    "buyer_name",
    "supplier_name",
    "procedure",
    "estimated_value_eur",
    "awarded_value_eur",
)


def run_case_study_evaluation(
    *,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
    scores_path: Path = DEFAULT_SCORES_PATH,
    flags_path: Path = DEFAULT_FLAGS_PATH,
    agent3_features_path: Path = DEFAULT_AGENT3_FEATURES_PATH,
    corpus_index_path: Path = DEFAULT_CORPUS_INDEX_PATH,
    output_dir: Path = DEFAULT_CASE_STUDIES_OUTPUT_DIR,
) -> dict[str, Any]:
    """Build ten traceable case studies from the frozen Agent2 base scenario."""
    import pandas as pd

    canonical = _read_parquet(canonical_path, "canonico Agent1/Agent2")
    scores = _read_parquet(scores_path, "scores base de Agent2")
    flags = _read_parquet(flags_path, "flags base de Agent2")
    agent3_features = _read_parquet(agent3_features_path, "features relacionales de Agent3")
    if not corpus_index_path.exists():
        raise FileNotFoundError(f"No existe el indice documental de Agent4: {corpus_index_path}")

    _require_columns(canonical, REQUIRED_CANONICAL_COLUMNS, "canonico")
    _require_columns(scores, REQUIRED_SCORE_COLUMNS, "scores")
    _require_columns(flags, REQUIRED_FLAG_COLUMNS, "flags")
    _require_columns(agent3_features, {"contract_key_canon"}, "features Agent3")
    _require_unique_keys(canonical, "canonico")
    _require_unique_keys(scores, "scores")
    _require_unique_keys(agent3_features, "features Agent3")

    merged = scores.merge(
        canonical,
        on="contract_key_canon",
        how="inner",
        validate="one_to_one",
        suffixes=("", "_canonical"),
    )
    if len(merged) != len(scores):
        raise ValueError("No todos los scores de Agent2 tienen contrato canonico asociado.")

    selections = select_case_studies(merged)
    features_by_key = agent3_features.set_index("contract_key_canon", drop=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = output_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()
    cases: list[dict[str, Any]] = []

    for position, selection in enumerate(selections, start=1):
        case_id = f"CS-{position:02d}"
        record = selection["record"]
        contract_key = str(record["contract_key_canon"])
        if contract_key not in features_by_key.index:
            raise ValueError(f"No hay features Agent3 para el caso seleccionado {contract_key}.")
        relationship_record = features_by_key.loc[contract_key]
        if isinstance(relationship_record, pd.DataFrame):
            relationship_record = relationship_record.iloc[0]
        case_flags = flags[flags["contract_key_canon"].astype(str).eq(contract_key)]
        case = _build_case_study(
            case_id=case_id,
            group=str(selection["group"]),
            group_rank=int(selection["group_rank"]),
            rationale=str(selection["rationale"]),
            record=record,
            flags=case_flags,
            relationships=relationship_record.to_dict(),
            corpus_index_path=corpus_index_path,
            generated_at=generated_at,
        )
        json_path = cases_dir / f"{case_id}.json"
        markdown_path = cases_dir / f"{case_id}.md"
        case["outputs"] = {"json": str(json_path), "markdown": str(markdown_path)}
        json_path.write_text(
            json.dumps(case, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(_case_to_markdown(case), encoding="utf-8")
        cases.append(case)

    report_json_path = output_dir / "case_studies_report.json"
    report_markdown_path = output_dir / "case_studies_report.md"
    report = {
        "dataset": "procurewatch_case_studies",
        "schema_version": CASE_STUDY_SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "inputs": {
            "canonical": _input_record(canonical_path, len(canonical)),
            "scores": _input_record(scores_path, len(scores)),
            "flags": _input_record(flags_path, len(flags)),
            "agent3_features": _input_record(agent3_features_path, len(agent3_features)),
            "corpus_index": _input_record(corpus_index_path, None),
        },
        "selection_policy": {
            "high_score": (
                "Cinco contratos con score maximo, priorizando parejas comprador-proveedor "
                "distintas para resolver empates."
            ),
            "medium_risk": (
                "Tres contratos de nivel medio, priorizando el mayor score y diversidad "
                "entre PLACE, BOE y OpenTender."
            ),
            "control": (
                "Dos contratos con score cero, sin flags y maxima evaluabilidad; uno de "
                "PLACE y otro de BOE."
            ),
        },
        "summary": _report_summary(cases),
        "cases": cases,
        "limitations": [
            "La seleccion usa la muestra reproducible de 3.437 contratos, no el canonico completo.",
            "No existen etiquetas de fraude ni revision experta externa para estos diez casos.",
            (
                "La ausencia de evidencia documental se registra sin sustituirla por "
                "contenido sintetico."
            ),
            "Los importes y codigos de procedimiento deben verificarse en la fuente original.",
        ],
        "decision_boundary": (
            "Las fichas evaluan priorizacion y explicacion para revision humana; "
            "no declaran fraude."
        ),
        "outputs": {
            "json": str(report_json_path),
            "markdown": str(report_markdown_path),
            "cases_dir": str(cases_dir),
        },
    }
    report_json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_markdown_path.write_text(_report_to_markdown(report), encoding="utf-8")
    return report


def select_case_studies(merged: Any) -> list[dict[str, Any]]:
    """Select five maximum-score, three medium-risk and two control contracts."""
    scores = merged.copy()
    scores["risk_score"] = scores["risk_score"].astype(float)
    scores["_risk_level_normalized"] = scores["risk_level"].map(_normalize_text)
    selected_keys: set[str] = set()
    result: list[dict[str, Any]] = []

    maximum = float(scores["risk_score"].max())
    high_candidates = _sort_candidates(scores[scores["risk_score"].eq(maximum)])
    high_rows = _select_distinct_pairs(high_candidates, 5, selected_keys)
    if len(high_rows) != 5:
        raise ValueError("No hay cinco contratos de score maximo para las fichas prioritarias.")
    _append_group(
        result,
        high_rows,
        group="high_score",
        rationale=f"Score maximo observado ({maximum:g}) y diversidad comprador-proveedor.",
    )

    medium_candidates = _sort_candidates(
        scores[scores["_risk_level_normalized"].isin({"MEDIO", "MEDIUM"})]
    )
    medium_rows = _select_distinct_sources(medium_candidates, 3, selected_keys)
    if len(medium_rows) != 3:
        raise ValueError("No hay tres contratos de riesgo medio con fuentes diferenciables.")
    _append_group(
        result,
        medium_rows,
        group="medium_risk",
        rationale="Nivel medio; mayor score disponible y diversidad de fuente.",
    )

    controls = scores[
        scores["risk_score"].eq(0)
        & scores["flags_count"].fillna(0).astype(int).eq(0)
        & ~scores["contract_key_canon"].astype(str).isin(selected_keys)
    ]
    control_rows = _select_controls(_sort_controls(controls), selected_keys)
    if len(control_rows) != 2:
        raise ValueError("No hay dos controles sin flags y con evaluabilidad suficiente.")
    _append_group(
        result,
        control_rows,
        group="control",
        rationale="Score cero, sin flags y maxima evaluabilidad disponible.",
    )
    return result


def _build_case_study(
    *,
    case_id: str,
    group: str,
    group_rank: int,
    rationale: str,
    record: dict[str, Any],
    flags: Any,
    relationships: dict[str, Any],
    corpus_index_path: Path,
    generated_at: str,
) -> dict[str, Any]:
    from procurewatch.agent4 import run_agent4_case_flow

    contract = {field: _json_ready(record.get(field)) for field in CONTRACT_FIELDS}
    active_rules = _json_list(record.get("top_flags"))
    not_evaluable_rules = _json_list(record.get("not_evaluable_rules"))
    rule_evidence = [
        {
            "flag_code": str(item.get("flag_code") or ""),
            "severity": _json_ready(item.get("severity")),
            "confidence": _json_ready(item.get("confidence")),
            "evidence_fields": _json_list(item.get("evidence_fields")),
            "evidence_text": str(item.get("evidence_text") or ""),
            "rule_version": str(item.get("rule_version") or ""),
        }
        for item in flags.sort_values("flag_code", kind="stable").to_dict("records")
    ]
    relationship_values = {
        field: _json_ready(relationships.get(field))
        for field in RELATIONSHIP_FIELDS
        if _has_value(relationships.get(field))
    }
    risk = {
        "risk_score": float(record["risk_score"]),
        "risk_level": str(record["risk_level"]),
        "flags_count": int(record["flags_count"]),
        "active_rules": active_rules,
        "evaluation_status": str(record["evaluation_status"]),
        "evaluable_rules_count": int(record["evaluable_rules_count"]),
        "not_evaluable_rules": not_evaluable_rules,
        "score_version": _json_ready(record.get("score_version")),
        "source_snapshot_id": _json_ready(record.get("source_snapshot_id")),
    }
    warnings = _case_warnings(
        contract=contract,
        active_rules=active_rules,
        not_evaluable_rules=not_evaluable_rules,
    )
    state = run_agent4_case_flow(
        contract_key_canon=str(contract["contract_key_canon"]),
        question="evidencia documental, reglas activadas y contexto contractual",
        corpus_index=corpus_index_path,
        contract_context=contract,
        agent2_score={
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "red_flags": active_rules,
            "evidence": rule_evidence,
        },
        agent3_metrics=relationship_values,
        warnings=warnings,
        use_services=False,
    )
    case_context = state.get("case_context", {})
    case_context = case_context if isinstance(case_context, dict) else {}
    all_warnings = _deduplicate(str(value) for value in state.get("warnings", []))
    evidenced_rules = {item["flag_code"] for item in rule_evidence}
    explanation_complete = set(active_rules) == evidenced_rules and bool(relationship_values)
    prioritization_correct = _selection_matches(group, risk)

    return {
        "dataset": "procurewatch_case_study",
        "schema_version": CASE_STUDY_SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "case_id": case_id,
        "selection": {
            "group": group,
            "group_rank": group_rank,
            "rationale": rationale,
        },
        "contract": contract,
        "risk": risk,
        "rule_evidence": rule_evidence,
        "relationships": relationship_values,
        "documentary_evidence": {
            "evidences": case_context.get("evidences", []),
            "citations": case_context.get("citations", []),
            "summary": case_context.get("summary"),
            "generation": case_context.get("generation", {}),
        },
        "warnings": all_warnings,
        "assessment": {
            "prioritization_criterion_met": prioritization_correct,
            "active_rules_with_evidence": len(evidenced_rules),
            "active_rules_count": len(active_rules),
            "rule_evidence_complete": set(active_rules) == evidenced_rules,
            "relationships_available": bool(relationship_values),
            "documentary_evidence_available": bool(case_context.get("evidences")),
            "explanation_complete": explanation_complete,
            "unsupported_fraud_claim": False,
        },
        "decision_boundary": _decision_boundary(group),
    }


def _report_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(cases)
    active_rules = sum(int(case["assessment"]["active_rules_count"]) for case in cases)
    evidenced_rules = sum(
        int(case["assessment"]["active_rules_with_evidence"]) for case in cases
    )
    groups = Counter(str(case["selection"]["group"]) for case in cases)
    sources = Counter(str(case["contract"].get("source") or "unknown") for case in cases)
    composition_ok = groups == {"high_score": 5, "medium_risk": 3, "control": 2}
    unique_contracts = len({str(case["contract"]["contract_key_canon"]) for case in cases})
    return {
        "cases_count": case_count,
        "unique_contracts": unique_contracts,
        "selection_breakdown": dict(groups),
        "source_breakdown": dict(sources),
        "active_rules_count": active_rules,
        "active_rules_with_evidence": evidenced_rules,
        "rule_evidence_coverage_ratio": _ratio(evidenced_rules, active_rules),
        "source_traceability_ratio": _boolean_ratio(
            cases,
            lambda case: bool(case["contract"].get("source"))
            and bool(case["contract"].get("source_record_id")),
        ),
        "relationships_available_ratio": _boolean_ratio(
            cases,
            lambda case: bool(case["assessment"]["relationships_available"]),
        ),
        "documentary_evidence_case_ratio": _boolean_ratio(
            cases,
            lambda case: bool(case["assessment"]["documentary_evidence_available"]),
        ),
        "explanation_complete_ratio": _boolean_ratio(
            cases,
            lambda case: bool(case["assessment"]["explanation_complete"]),
        ),
        "prioritization_criteria_ratio": _boolean_ratio(
            cases,
            lambda case: bool(case["assessment"]["prioritization_criterion_met"]),
        ),
        "unsupported_fraud_claims": sum(
            int(bool(case["assessment"]["unsupported_fraud_claim"])) for case in cases
        ),
        "warnings_count": sum(len(case["warnings"]) for case in cases),
        "practical_validation_passed": bool(
            case_count == 10
            and unique_contracts == 10
            and composition_ok
            and active_rules == evidenced_rules
            and all(case["assessment"]["explanation_complete"] for case in cases)
            and not any(case["assessment"]["unsupported_fraud_claim"] for case in cases)
        ),
    }


def _select_distinct_pairs(
    candidates: Any,
    count: int,
    selected_keys: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    records = candidates.to_dict("records")
    for record in records:
        pair = (
            _normalize_text(record.get("buyer_name")),
            _normalize_text(record.get("supplier_name")),
        )
        if pair in seen_pairs:
            continue
        _add_selected(rows, record, selected_keys)
        seen_pairs.add(pair)
        if len(rows) == count:
            return rows
    for record in records:
        _add_selected(rows, record, selected_keys)
        if len(rows) == count:
            break
    return rows


def _select_distinct_sources(
    candidates: Any,
    count: int,
    selected_keys: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    records = candidates.to_dict("records")
    for record in records:
        source = _normalize_text(record.get("source"))
        if source in seen_sources:
            continue
        _add_selected(rows, record, selected_keys)
        seen_sources.add(source)
        if len(rows) == count:
            return rows
    for record in records:
        _add_selected(rows, record, selected_keys)
        if len(rows) == count:
            break
    return rows


def _select_controls(candidates: Any, selected_keys: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    records = candidates.to_dict("records")
    for preferred_source in ("PLACE", "BOE"):
        for record in records:
            if _normalize_text(record.get("source")) != preferred_source:
                continue
            _add_selected(rows, record, selected_keys)
            break
    if len(rows) < 2:
        for record in records:
            _add_selected(rows, record, selected_keys)
            if len(rows) == 2:
                break
    return rows


def _add_selected(
    rows: list[dict[str, Any]],
    record: dict[str, Any],
    selected_keys: set[str],
) -> None:
    contract_key = str(record.get("contract_key_canon") or "")
    if not contract_key or contract_key in selected_keys:
        return
    rows.append(record)
    selected_keys.add(contract_key)


def _append_group(
    target: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    group: str,
    rationale: str,
) -> None:
    for group_rank, record in enumerate(rows, start=1):
        target.append(
            {
                "group": group,
                "group_rank": group_rank,
                "rationale": rationale,
                "record": record,
            }
        )


def _sort_candidates(dataframe: Any) -> Any:
    return dataframe.sort_values(
        ["risk_score", "evaluable_rules_count", "contract_key_canon"],
        ascending=[False, False, True],
        kind="stable",
    )


def _sort_controls(dataframe: Any) -> Any:
    return dataframe.sort_values(
        ["evaluable_rules_count", "contract_key_canon"],
        ascending=[False, True],
        kind="stable",
    )


def _case_warnings(
    *,
    contract: dict[str, Any],
    active_rules: list[str],
    not_evaluable_rules: list[str],
) -> list[str]:
    warnings = [
        f"{rule} no fue evaluable por falta de los campos requeridos."
        for rule in not_evaluable_rules
    ]
    missing = [field for field in IMPORTANT_FIELDS if not _has_value(contract.get(field))]
    if missing:
        warnings.append(f"Campos fuente ausentes o vacios: {', '.join(missing)}.")
    if "RF-05" in active_rules:
        warnings.append(
            "La comparabilidad entre importe estimado y adjudicado debe verificarse en origen "
            "por posibles lotes, unidades o agregaciones."
        )
    if {"RF-03", "RF-04"}.intersection(active_rules):
        warnings.append(
            "Agent2 calcula las senales relacionales con nombres normalizados y cuota de "
            "importe; Agent3 usa IDs del grafo y cuota de contratos, por lo que sus valores "
            "son contexto complementario y no tienen que coincidir."
        )
    if not active_rules:
        warnings.append(
            "Score cero significa ausencia de senales con los datos evaluables, "
            "no ausencia de riesgo."
        )
    return warnings


def _selection_matches(group: str, risk: dict[str, Any]) -> bool:
    if group == "high_score":
        return float(risk["risk_score"]) > 0 and str(risk["risk_level"]).lower() == "alto"
    if group == "medium_risk":
        return _normalize_text(risk["risk_level"]) in {"MEDIO", "MEDIUM"}
    return float(risk["risk_score"]) == 0 and int(risk["flags_count"]) == 0


def _decision_boundary(group: str) -> str:
    if group == "control":
        return (
            "Este contrato se usa como control comparativo por no activar senales con los "
            "datos evaluables. No se declara ausencia de riesgo ni fraude."
        )
    return "El score prioriza este contrato para revision humana. No se declara fraude."


def _case_to_markdown(case: dict[str, Any]) -> str:
    contract = case["contract"]
    risk = case["risk"]
    relationships = case["relationships"]
    documentary = case["documentary_evidence"]
    lines = [
        f"# {case['case_id']} - {_group_label(case['selection']['group'])}",
        "",
        f"- Contrato: `{contract['contract_key_canon']}`",
        f"- Fuente: `{contract.get('source')}` / `{contract.get('source_record_id')}`",
        f"- Comprador: {contract.get('buyer_name') or 'no disponible'}",
        f"- Adjudicatario: {contract.get('supplier_name') or 'no disponible'}",
        f"- Procedimiento: {contract.get('procedure') or 'no disponible'}",
        f"- Importe estimado: {_format_amount(contract.get('estimated_value_eur'))}",
        f"- Importe adjudicado: {_format_amount(contract.get('awarded_value_eur'))}",
        f"- Score/nivel: {risk['risk_score']:.0f} / {risk['risk_level']}",
        f"- Reglas activadas: {', '.join(risk['active_rules']) or 'ninguna'}",
        "",
        "## Evidencia de reglas",
        "",
    ]
    if case["rule_evidence"]:
        lines.extend(
            f"- **{item['flag_code']}**: {item['evidence_text']}"
            for item in case["rule_evidence"]
        )
    else:
        lines.append("- No hay reglas activadas en los datos evaluables.")
    lines.extend(["", "## Relaciones", ""])
    for field in (
        "buyer_supplier_recurrence",
        "buyer_supplier_contract_share",
        "buyer_degree",
        "supplier_degree",
        "supplier_contracts_count",
        "community_id",
        "community_size",
    ):
        if field in relationships:
            lines.append(f"- `{field}`: {relationships[field]}")
    lines.extend(
        [
            "",
            "## Evidencia documental",
            "",
            f"- Evidencias: {len(documentary.get('evidences', []))}",
            f"- Citas: {len(documentary.get('citations', []))}",
            f"- Lectura: {documentary.get('summary') or 'no disponible'}",
            "",
            "## Advertencias",
            "",
        ]
    )
    lines.extend(f"- {warning}" for warning in case["warnings"])
    lines.extend(["", f"**Limite de decision:** {case['decision_boundary']}", ""])
    return "\n".join(lines)


def _report_to_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Evaluacion de diez fichas de caso",
        "",
        f"- Casos: **{summary['cases_count']}**",
        f"- Composicion: `{summary['selection_breakdown']}`",
        (
            "- Cobertura de evidencia de reglas: "
            f"{_format_ratio(summary['rule_evidence_coverage_ratio'])}"
        ),
        f"- Relaciones disponibles: {_format_ratio(summary['relationships_available_ratio'])}",
        (
            "- Casos con evidencia documental: "
            f"{_format_ratio(summary['documentary_evidence_case_ratio'])}"
        ),
        (
            "- Validacion practica: "
            f"**{'pass' if summary['practical_validation_passed'] else 'review'}**"
        ),
        "",
        "| Caso | Grupo | Fuente | Score | Nivel | Reglas | Evidencia doc. |",
        "|---|---|---|---:|---|---|---:|",
    ]
    for case in report["cases"]:
        risk = case["risk"]
        lines.append(
            f"| {case['case_id']} | {case['selection']['group']} | "
            f"{case['contract'].get('source')} | {risk['risk_score']:.0f} | "
            f"{risk['risk_level']} | {', '.join(risk['active_rules']) or 'ninguna'} | "
            f"{len(case['documentary_evidence'].get('evidences', []))} |"
        )
    lines.extend(["", "## Limitaciones", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(["", f"**Limite de decision:** {report['decision_boundary']}", ""])
    return "\n".join(lines)


def _read_parquet(path: Path, label: str) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"No existe {label}: {path}")
    import pandas as pd

    return pd.read_parquet(path)


def _require_columns(dataframe: Any, required: set[str], label: str) -> None:
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f"Faltan columnas en {label}: {sorted(missing)}")


def _require_unique_keys(dataframe: Any, label: str) -> None:
    keys = dataframe["contract_key_canon"].astype("string").fillna("").str.strip()
    duplicates = keys[keys.duplicated(keep=False)]
    if not duplicates.empty:
        raise ValueError(f"{label} contiene claves de contrato duplicadas.")


def _input_record(path: Path, rows: int | None) -> dict[str, Any]:
    return {"path": str(path), "rows": rows, "sha256": _sha256(path)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _json_ready(value: object) -> object:
    if value is None:
        return None
    try:
        import pandas as pd

        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return _json_ready(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        import pandas as pd

        return not bool(pd.isna(value))
    except (TypeError, ValueError):
        return True


def _normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = text.encode("ascii", "ignore").decode("ascii").upper()
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text).strip()


def _deduplicate(values: Any) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _ratio(numerator: int, denominator: int) -> float | None:
    return float(numerator / denominator) if denominator else None


def _boolean_ratio(cases: list[dict[str, Any]], predicate: Any) -> float | None:
    return _ratio(sum(1 for case in cases if predicate(case)), len(cases))


def _format_amount(value: object) -> str:
    if value is None:
        return "no disponible"
    try:
        return f"{float(value):,.2f} EUR"
    except (TypeError, ValueError):
        return str(value)


def _format_ratio(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"


def _group_label(value: object) -> str:
    return {
        "high_score": "score maximo",
        "medium_risk": "riesgo medio",
        "control": "control",
    }.get(str(value), str(value))


__all__ = [
    "CASE_STUDY_SCHEMA_VERSION",
    "DEFAULT_CASE_STUDIES_OUTPUT_DIR",
    "run_case_study_evaluation",
    "select_case_studies",
]
