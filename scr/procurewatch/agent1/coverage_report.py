from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .analytical_schema import CONTRACT_REQUIRED_FIELDS, CONTRACT_SCHEMA

CRITICAL_OCDS_FIELDS = (
    "id_contrato",
    "organismo_contratante",
    "procedimiento",
    "cpv_codigo",
    "importe_adjudicado",
    "fecha_publicacion",
    "nombre_adjudicatario",
)


def build_agent1_coverage_report(
    *,
    contracts_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Profile current Agent1 analytical coverage without treating missing data as success."""
    import pandas as pd

    if not contracts_path.exists():
        raise FileNotFoundError(contracts_path)

    contracts = pd.read_parquet(contracts_path)
    missing_schema_fields = [
        field for field in CONTRACT_REQUIRED_FIELDS if field not in contracts.columns
    ]
    field_coverage: dict[str, dict[str, Any]] = {}
    for field in CONTRACT_REQUIRED_FIELDS:
        if field not in contracts.columns:
            field_coverage[field] = {
                "owner": CONTRACT_SCHEMA[field]["owner"],
                "present": 0,
                "missing": int(len(contracts)),
                "coverage_ratio": 0.0 if len(contracts) else None,
                "status": "missing_from_schema",
            }
            continue
        present = _present_mask(contracts[field])
        present_count = int(present.sum())
        coverage_ratio = round(present_count / len(contracts), 6) if len(contracts) else None
        field_coverage[field] = {
            "owner": CONTRACT_SCHEMA[field]["owner"],
            "present": present_count,
            "missing": int(len(contracts) - present_count),
            "coverage_ratio": coverage_ratio,
            "status": _coverage_status(coverage_ratio),
        }

    critical_present_cells = sum(field_coverage[field]["present"] for field in CRITICAL_OCDS_FIELDS)
    critical_total_cells = len(contracts) * len(CRITICAL_OCDS_FIELDS)
    critical_complete_rows = 0
    if len(contracts) and not missing_schema_fields:
        critical_masks = [_present_mask(contracts[field]) for field in CRITICAL_OCDS_FIELDS]
        complete = critical_masks[0]
        for mask in critical_masks[1:]:
            complete &= mask
        critical_complete_rows = int(complete.sum())

    critical_ratio = (
        round(critical_present_cells / critical_total_cells, 6) if critical_total_cells else None
    )
    nif_present = field_coverage["nif_adjudicatario"]["present"]
    nif_ratio = round(nif_present / len(contracts), 6) if len(contracts) else None

    publication = pd.to_datetime(contracts.get("fecha_publicacion"), errors="coerce")
    award = pd.to_datetime(contracts.get("fecha_adjudicacion"), errors="coerce")
    comparable = publication.notna() & award.notna()
    comparable_rows = int(comparable.sum())
    coherent_rows = int((comparable & (publication <= award)).sum())
    temporal_ratio = round(coherent_rows / comparable_rows, 6) if comparable_rows else None

    numeric_columns = ("importe_estimado", "importe_adjudicado")
    negative_amounts = {
        field: int((pd.to_numeric(contracts[field], errors="coerce") < 0).sum())
        for field in numeric_columns
        if field in contracts.columns
    }
    duplicate_contract_ids = (
        int(contracts["id_contrato"].duplicated().sum())
        if "id_contrato" in contracts.columns
        else None
    )
    sources_present = _source_names(contracts)

    quality_metrics = {
        "ocds_critical_completeness": {
            "fields": list(CRITICAL_OCDS_FIELDS),
            "coverage_ratio": critical_ratio,
            "complete_rows": critical_complete_rows,
            "complete_rows_ratio": (
                round(critical_complete_rows / len(contracts), 6) if len(contracts) else None
            ),
            "target_ratio": 0.90,
            "status": _target_status(critical_ratio, 0.90),
        },
        "supplier_nif_coverage": {
            "present_rows": nif_present,
            "coverage_ratio": nif_ratio,
            "target_ratio": 0.85,
            "status": _target_status(nif_ratio, 0.85),
            "note": "BOE no aporta NIF del adjudicatario en el dataset procesado actual.",
        },
        "temporal_coherence": {
            "comparable_rows": comparable_rows,
            "coherent_rows": coherent_rows,
            "incoherent_rows": comparable_rows - coherent_rows,
            "not_evaluable_rows": int(len(contracts) - comparable_rows),
            "coherence_ratio": temporal_ratio,
            "target_ratio": 0.98,
            "status": _target_status(temporal_ratio, 0.98),
            "note": "La métrica no es evaluable sin fecha de adjudicación.",
        },
    }

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": {
            "dataset": str(contracts_path),
            "sources_present": sorted(sources_present),
            "rows": int(len(contracts)),
            "domain": "CPV 71",
            "warning": (
                "Este informe describe el dataset analítico actual. "
                "No acredita integración completa "
                "de PLACE u OpenTender si esas fuentes no aparecen en fuentes_cruzadas."
            ),
        },
        "schema": {
            "required_contract_fields": len(CONTRACT_REQUIRED_FIELDS),
            "present_contract_fields": len(CONTRACT_REQUIRED_FIELDS) - len(missing_schema_fields),
            "missing_fields": missing_schema_fields,
            "status": "complete" if not missing_schema_fields else "incomplete",
        },
        "field_coverage": field_coverage,
        "quality_metrics": quality_metrics,
        "data_consistency": {
            "duplicate_contract_ids": duplicate_contract_ids,
            "negative_amounts": negative_amounts,
        },
        "implementation_requirements": [
            {
                "requirement": "Integración BOE, PLACE y OpenTender",
                "status": (
                    "complete"
                    if {"boe", "place", "opentender"}.issubset(sources_present)
                    else "pending"
                ),
            },
            {
                "requirement": "Carga analítica en PostgreSQL",
                "status": "pending",
                "note": "No se acredita mediante el Parquet analizado.",
            },
            {
                "requirement": "Actualización incremental por registros",
                "status": "partial",
                "note": (
                    "Existe batch y reutilización de caché, "
                    "pero no carga incremental en base de datos."
                ),
            },
        ],
    }
    report["overall_status"] = _overall_status(report)

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "agent1_coverage_report.json"
    markdown_path = output_dir / "agent1_coverage_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_to_markdown(report), encoding="utf-8")
    report["outputs"] = {"json": str(json_path), "markdown": str(markdown_path)}
    return report


def _present_mask(series: Any) -> Any:
    import pandas as pd

    def is_present(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) > 0
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    return series.map(is_present)


def _source_names(contracts: Any) -> set[str]:
    sources: set[str] = set()
    if "fuentes_cruzadas" not in contracts.columns:
        return sources
    for value in contracts["fuentes_cruzadas"]:
        if hasattr(value, "tolist") and not isinstance(value, str):
            value = value.tolist()
        if isinstance(value, (list, tuple, set)):
            sources.update(str(item).strip().lower() for item in value if str(item).strip())
    return sources


def _coverage_status(ratio: float | None) -> str:
    if ratio is None:
        return "not_evaluable"
    if ratio >= 0.90:
        return "high"
    if ratio > 0:
        return "partial"
    return "unavailable"


def _target_status(ratio: float | None, target: float) -> str:
    if ratio is None:
        return "not_evaluable"
    return "met" if ratio > target else "not_met"


def _overall_status(report: dict[str, Any]) -> str:
    metric_statuses = {metric["status"] for metric in report["quality_metrics"].values()}
    implementation_statuses = {item["status"] for item in report["implementation_requirements"]}
    if report["schema"]["status"] != "complete":
        return "incomplete"
    if metric_statuses == {"met"} and implementation_statuses == {"complete"}:
        return "complete"
    return "partial"


def _to_markdown(report: dict[str, Any]) -> str:
    scope = report["scope"]
    lines = [
        "# Informe de cobertura y calidad del Agente 1",
        "",
        f"- Estado global: **{report['overall_status']}**",
        f"- Filas analizadas: **{scope['rows']}**",
        f"- Fuentes presentes: **{', '.join(sorted(scope['sources_present'])) or 'ninguna'}**",
        f"- Dominio: **{scope['domain']}**",
        "",
        "## Métricas exigidas",
        "",
        "| Métrica | Resultado | Objetivo | Estado |",
        "|---|---:|---:|---|",
    ]
    metrics = report["quality_metrics"]
    for name, metric in metrics.items():
        ratio = metric.get("coverage_ratio", metric.get("coherence_ratio"))
        shown_ratio = "no evaluable" if ratio is None else f"{ratio:.2%}"
        lines.append(
            f"| `{name}` | {shown_ratio} | > {metric['target_ratio']:.0%} | {metric['status']} |"
        )

    lines.extend(
        [
            "",
            "## Cobertura de campos del modelo CONTRATO",
            "",
            "| Campo | Responsable | Presentes | Cobertura | Estado |",
            "|---|---|---:|---:|---|",
        ]
    )
    for field, coverage in report["field_coverage"].items():
        ratio = coverage["coverage_ratio"]
        shown_ratio = "n/a" if ratio is None else f"{ratio:.2%}"
        lines.append(
            f"| `{field}` | {coverage['owner']} | {coverage['present']} | "
            f"{shown_ratio} | {coverage['status']} |"
        )

    lines.extend(["", "## Requisitos todavía pendientes", ""])
    for requirement in report["implementation_requirements"]:
        note = f" — {requirement['note']}" if requirement.get("note") else ""
        lines.append(f"- **{requirement['status']}**: {requirement['requirement']}{note}")
    lines.extend(["", f"> {scope['warning']}", ""])
    return "\n".join(lines)
