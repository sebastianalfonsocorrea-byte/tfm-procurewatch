from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .mvp_pipeline import (
    DEFAULT_CONCENTRATION_THRESHOLD,
    DEFAULT_DEVIATION_THRESHOLD,
    DEFAULT_RECURRENCE_THRESHOLD,
    DEFAULT_TEMPORAL_DAYS_THRESHOLD,
    RULE_CODES,
    run_agent2_mvp,
)

EVALUATION_SCHEMA_VERSION = "1.0.0"
SCENARIO_FACTORS = {"lower": 0.9, "base": 1.0, "upper": 1.1}


def run_agent2_evaluation(
    *,
    input_path: Path,
    output_dir: Path,
    agent3_features_path: Path | None = None,
) -> dict[str, Any]:
    """Run Agent2 under three threshold profiles and compare them with the base run."""
    import pandas as pd

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_reports: dict[str, dict[str, Any]] = {}
    scenario_scores: dict[str, Any] = {}

    for scenario, factor in SCENARIO_FACTORS.items():
        scenario_dir = output_dir / scenario
        thresholds = _thresholds(factor)
        run_report = run_agent2_mvp(
            input_path=input_path,
            output_dir=scenario_dir,
            agent3_features_path=agent3_features_path,
            **thresholds,
        )
        scores = pd.read_parquet(run_report["outputs"]["risk_scores"])
        scenario_scores[scenario] = scores
        scenario_reports[scenario] = {
            "factor": factor,
            "thresholds": thresholds,
            "rows": int(run_report["rows"]),
            "fully_evaluable_rows": int(run_report["fully_evaluable_rows"]),
            "partially_evaluable_rows": int(run_report["partially_evaluable_rows"]),
            "not_evaluable_rows": int(run_report["not_evaluable_rows"]),
            "activated_contract_rows": int(run_report["activated_contract_rows"]),
            "activated_flags": int(run_report["activated_flags"]),
            "flag_frequency": _flag_frequency(run_report, rows=len(scores)),
            "risk_level_breakdown": {
                str(key): int(value)
                for key, value in run_report["risk_level_breakdown"].items()
            },
            "risk_band_distribution": _risk_band_distribution(scores),
            "risk_score_distribution": _score_distribution(scores),
            "rule_evaluability": run_report["rule_evaluability"],
            "missing_fields": run_report["missing_fields"],
            "agent3_features_status": run_report["agent3_features_status"],
            "outputs": {
                **run_report["outputs"],
                "report": run_report["report_path"],
            },
        }

    base_scores = scenario_scores["base"]
    comparisons = {
        scenario: _compare_scores(base_scores, scenario_scores[scenario])
        for scenario in ("lower", "upper")
    }
    json_path = output_dir / "agent2_evaluation_report.json"
    markdown_path = output_dir / "agent2_evaluation_report.md"
    report = {
        "dataset": "agent2_threshold_sensitivity_evaluation",
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input": {
            "path": str(input_path),
            "rows": int(len(base_scores)),
            "source_snapshot_id": _base_snapshot(output_dir),
            "scope": "reproducible_sample",
        },
        "method": {
            "rules": RULE_CODES,
            "scenario_factors": SCENARIO_FACTORS,
            "comparison_reference": "base",
            "discrete_threshold_note": (
                "RF-03 recurrence counts and RF-06 resolution days are discrete; "
                "multipliers can map to the same effective integer boundary."
            ),
        },
        "scenarios": scenario_reports,
        "comparisons_to_base": comparisons,
        "limitations": [
            "The evaluation uses the 3,437-row reproducible sample, not the 51,720-row full run.",
            "The results prioritise human review and do not classify or confirm fraud.",
            "The sensitivity analysis evaluates deterministic rules without labelled outcomes.",
        ],
        "outputs": {"json": str(json_path), "markdown": str(markdown_path)},
    }
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_to_markdown(report), encoding="utf-8")
    return report


def _thresholds(factor: float) -> dict[str, float]:
    return {
        "recurrence_threshold": DEFAULT_RECURRENCE_THRESHOLD * factor,
        "concentration_threshold": DEFAULT_CONCENTRATION_THRESHOLD * factor,
        "deviation_threshold": DEFAULT_DEVIATION_THRESHOLD * factor,
        "temporal_days_threshold": DEFAULT_TEMPORAL_DAYS_THRESHOLD * factor,
    }


def _flag_frequency(run_report: dict[str, Any], *, rows: int) -> dict[str, dict[str, object]]:
    breakdown = run_report.get("flag_breakdown", {})
    return {
        code: {
            "count": int(breakdown.get(code, 0)),
            "contract_ratio": int(breakdown.get(code, 0)) / rows if rows else None,
        }
        for code in RULE_CODES
    }


def _score_distribution(scores: Any) -> dict[str, float | int | None]:
    import pandas as pd

    values = pd.to_numeric(scores["risk_score"], errors="coerce").dropna()
    if values.empty:
        return {"count": 0, "min": None, "q1": None, "median": None, "mean": None,
                "q3": None, "max": None, "std": None}
    return {
        "count": int(len(values)),
        "min": float(values.min()),
        "q1": float(values.quantile(0.25)),
        "median": float(values.median()),
        "mean": float(values.mean()),
        "q3": float(values.quantile(0.75)),
        "max": float(values.max()),
        "std": float(values.std(ddof=0)),
    }


def _risk_band_distribution(scores: Any) -> dict[str, int]:
    import pandas as pd

    values = pd.to_numeric(scores["risk_score"], errors="coerce")
    return {
        "no_flags": int(values.eq(0).sum()),
        "low_positive": int(values.gt(0).mul(values.lt(25)).sum()),
        "medium": int(values.ge(25).mul(values.lt(50)).sum()),
        "high": int(values.ge(50).mul(values.lt(75)).sum()),
        "critical": int(values.ge(75).sum()),
    }


def _compare_scores(base: Any, candidate: Any) -> dict[str, object]:
    import pandas as pd

    columns = ["contract_key_canon", "risk_score", "risk_level", "top_flags"]
    merged = base[columns].merge(
        candidate[columns],
        on="contract_key_canon",
        how="inner",
        suffixes=("_base", "_candidate"),
        validate="one_to_one",
    )
    score_delta = (
        pd.to_numeric(merged["risk_score_candidate"], errors="coerce")
        - pd.to_numeric(merged["risk_score_base"], errors="coerce")
    )
    score_changed = score_delta.abs().gt(1e-9)
    level_changed = merged["risk_level_base"].ne(merged["risk_level_candidate"])
    flags_changed = merged["top_flags_base"].map(_flag_set).ne(
        merged["top_flags_candidate"].map(_flag_set)
    )
    rows = int(len(merged))
    return {
        "matched_rows": rows,
        "score_changed_rows": int(score_changed.sum()),
        "score_unchanged_ratio": _unchanged_ratio(score_changed, rows),
        "risk_level_changed_rows": int(level_changed.sum()),
        "risk_level_unchanged_ratio": _unchanged_ratio(level_changed, rows),
        "flag_set_changed_rows": int(flags_changed.sum()),
        "flag_set_unchanged_ratio": _unchanged_ratio(flags_changed, rows),
        "mean_absolute_score_delta": float(score_delta.abs().mean()) if rows else None,
        "mean_score_delta": float(score_delta.mean()) if rows else None,
    }


def _flag_set(value: object) -> str:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = []
    return "|".join(sorted(str(item) for item in parsed))


def _unchanged_ratio(changed: Any, rows: int) -> float | None:
    return float((~changed).sum() / rows) if rows else None


def _base_snapshot(output_dir: Path) -> str:
    payload = json.loads(
        (output_dir / "base" / "agent2_run_report.json").read_text(encoding="utf-8")
    )
    return str(payload["source_snapshot_id"])


def _to_markdown(report: dict[str, Any]) -> str:
    base = report["scenarios"]["base"]
    lines = [
        "# Evaluacion de sensibilidad de Agent2",
        "",
        f"- Contratos de la muestra: {report['input']['rows']}",
        f"- Snapshot: `{report['input']['source_snapshot_id']}`",
        "- Reglas: RF-01 a RF-06",
        "- Escenarios: umbrales x0.9, x1.0 y x1.1",
        "",
        "## Evaluabilidad del escenario base",
        "",
        "| Regla | Evaluables | No evaluables | Cobertura |",
        "|---|---:|---:|---:|",
    ]
    for code in RULE_CODES:
        item = base["rule_evaluability"][code]
        lines.append(
            f"| {code} | {item['evaluable_rows']} | {item['not_evaluable_rows']} | "
            f"{_pct(item['evaluable_ratio'])} |"
        )
    lines.extend(
        [
            "",
            "## Frecuencia de flags",
            "",
            "| Regla | -10 % | Base | +10 % |",
            "|---|---:|---:|---:|",
        ]
    )
    for code in RULE_CODES:
        lines.append(
            f"| {code} | {report['scenarios']['lower']['flag_frequency'][code]['count']} | "
            f"{base['flag_frequency'][code]['count']} | "
            f"{report['scenarios']['upper']['flag_frequency'][code]['count']} |"
        )
    lines.extend(
        [
            "",
            "## Distribucion de riesgo",
            "",
            "| Escenario | Sin flags | Bajo >0 | Medio | Alto | Critico | Media score |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for scenario in SCENARIO_FACTORS:
        item = report["scenarios"][scenario]
        bands = item["risk_band_distribution"]
        lines.append(
            f"| {scenario} | {bands['no_flags']} | {bands['low_positive']} | "
            f"{bands['medium']} | {bands['high']} | {bands['critical']} | "
            f"{item['risk_score_distribution']['mean']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Estabilidad frente al escenario base",
            "",
            "| Escenario | Score sin cambio | Nivel sin cambio | Flags sin cambio |",
            "|---|---:|---:|---:|",
        ]
    )
    for scenario in ("lower", "upper"):
        item = report["comparisons_to_base"][scenario]
        lines.append(
            f"| {scenario} | {_pct(item['score_unchanged_ratio'])} | "
            f"{_pct(item['risk_level_unchanged_ratio'])} | "
            f"{_pct(item['flag_set_unchanged_ratio'])} |"
        )
    lines.extend(["", "## Campos ausentes o no validos", "", "| Campo | Filas |", "|---|---:|"])
    for field, count in base["missing_fields"].items():
        lines.append(f"| `{field}` | {count} |")
    lines.extend(["", "## Limitaciones", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def _pct(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"


__all__ = ["run_agent2_evaluation"]
