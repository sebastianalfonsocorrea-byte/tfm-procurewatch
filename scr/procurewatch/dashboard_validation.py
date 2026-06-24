from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agent3 import build_demo_kpis, load_agent3_demo_data, missing_demo_artifacts
from .integrated_demo import (
    DEMO_CASE_CONTEXT_FILENAME,
    DEMO_CONTRACT_KEY,
    DEMO_CORPUS_INDEX,
    DEMO_OUTPUT_DIR,
    DEMO_QUESTION,
    run_integrated_demo,
)

DASHBOARD_APP_PATH = Path("frontend/agent3_demo.py")
DASHBOARD_VALIDATION_REPORT_FILENAME = "dashboard_validation_report.json"
DASHBOARD_VALIDATION_SCHEMA_VERSION = "dashboard_validation_report_v1"
DASHBOARD_CAPTURE_RECOMMENDATIONS = [
    "Resumen",
    "Contratos priorizados",
    "Caso seleccionado",
    "Relaciones",
    "Evidencias",
    "Trazabilidad",
    "Metodologia",
]


def validate_dashboard_demo(
    *,
    output_dir: Path = DEMO_OUTPUT_DIR,
    case_context_path: Path | None = None,
    report_path: Path | None = None,
    contract_key_canon: str = DEMO_CONTRACT_KEY,
    question: str = DEMO_QUESTION,
    corpus_index: Path = DEMO_CORPUS_INDEX,
    app_path: Path = DASHBOARD_APP_PATH,
    regenerate: bool = True,
    run_streamlit: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_case_context_path = case_context_path or output_dir / DEMO_CASE_CONTEXT_FILENAME
    resolved_report_path = report_path or output_dir / DASHBOARD_VALIDATION_REPORT_FILENAME

    integrated_report = None
    if regenerate:
        integrated_report = run_integrated_demo(
            output_dir=output_dir,
            contract_key_canon=contract_key_canon,
            question=question,
            corpus_index=corpus_index,
        )

    data, kpis, data_error = _load_agent3_dashboard_data(output_dir)
    case_context, case_error = _load_case_context(resolved_case_context_path)
    source_text = app_path.read_text(encoding="utf-8") if app_path.exists() else ""
    streamlit_result = (
        _run_streamlit_headless(
            app_path=app_path,
            output_dir=output_dir,
            case_context_path=resolved_case_context_path,
        )
        if run_streamlit
        else {"executed": False, "exceptions": [], "metrics_count": None, "tabs_count": None}
    )

    checks = _build_checks(
        output_dir=output_dir,
        case_context_path=resolved_case_context_path,
        app_path=app_path,
        kpis=kpis,
        data_error=data_error,
        case_context=case_context,
        case_error=case_error,
        source_text=source_text,
        streamlit_result=streamlit_result,
        contract_key_canon=contract_key_canon,
    )
    report = {
        "schema_version": DASHBOARD_VALIDATION_SCHEMA_VERSION,
        "status": "ready" if all(check["passed"] for check in checks) else "failed",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "demo_type": "synthetic_offline",
        "contract_key_canon": contract_key_canon,
        "output_dir": str(output_dir),
        "case_context_path": str(resolved_case_context_path),
        "dashboard_app": str(app_path),
        "artifacts": {
            "integrated_demo_report": _integrated_report_path(integrated_report, output_dir),
            "dashboard_validation_report": str(resolved_report_path),
        },
        "kpis": kpis,
        "case_summary": _case_summary(case_context),
        "checks": checks,
        "streamlit_headless": streamlit_result,
        "commands": _defense_commands(output_dir, resolved_case_context_path),
        "capture_recommendations": DASHBOARD_CAPTURE_RECOMMENDATIONS,
        "limitations": [
            "Dashboard local de demo; no es plataforma productiva.",
            "Demo sintetica/offline regenerada desde codigo, sin servicios externos obligatorios.",
            "El sistema prioriza revision humana y no declara fraude.",
        ],
    }
    resolved_report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _load_agent3_dashboard_data(
    output_dir: Path,
) -> tuple[object | None, dict[str, int], str | None]:
    try:
        data = load_agent3_demo_data(output_dir)
    except Exception as exc:
        return None, {}, str(exc)
    return data, build_demo_kpis(data), None


def _load_case_context(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"No existe la ficha Agent4: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return {}, f"No se pudo leer JSON Agent4: {exc}"


def _build_checks(
    *,
    output_dir: Path,
    case_context_path: Path,
    app_path: Path,
    kpis: dict[str, int],
    data_error: str | None,
    case_context: dict[str, Any],
    case_error: str | None,
    source_text: str,
    streamlit_result: dict[str, Any],
    contract_key_canon: str,
) -> list[dict[str, object]]:
    case = _case_context(case_context)
    visible_text = source_text.lower()
    return [
        _check(
            "agent3_artifacts_complete",
            not missing_demo_artifacts(output_dir) and data_error is None,
            data_error or "Artefactos Agent3 completos.",
        ),
        _check(
            "agent4_case_context_exists",
            case_context_path.exists() and case_error is None,
            case_error or str(case_context_path),
        ),
        _check(
            "case_context_matches_contract",
            _case_contract_key(case_context) == contract_key_canon,
            f"Contrato en ficha: {_case_contract_key(case_context) or 'n/a'}",
        ),
        _check(
            "dashboard_kpis_loadable",
            kpis.get("contracts", 0) > 0
            and kpis.get("edges", 0) > 0
            and kpis.get("agent2_features", 0) > 0,
            f"KPIs: {kpis}",
        ),
        _check(
            "agent2_score_loadable",
            _risk_score(case_context) is not None and bool(_red_flags(case_context)),
            f"risk_score={_risk_score(case_context)} red_flags={len(_red_flags(case_context))}",
        ),
        _check(
            "agent3_metrics_loadable",
            bool(case.get("agent3_metrics_used")),
            f"metricas={len(case.get('agent3_metrics_used', {}))}",
        ),
        _check(
            "agent4_evidence_loadable",
            bool(case.get("evidences")) and bool(case.get("citations")),
            f"evidencias={len(case.get('evidences', []))} citas={len(case.get('citations', []))}",
        ),
        _check(
            "visible_text_keeps_review_boundary",
            "no declara fraude" in visible_text
            and "priorizar" in visible_text
            and "revision" in visible_text,
            "El texto visible habla de priorizacion/revision humana y no declara fraude.",
        ),
        _check(
            "streamlit_headless_renders",
            streamlit_result["executed"] and not streamlit_result["exceptions"],
            "; ".join(streamlit_result["exceptions"]) or "Streamlit renderiza sin excepciones.",
        ),
        _check(
            "dashboard_app_exists",
            app_path.exists(),
            str(app_path),
        ),
    ]


def _run_streamlit_headless(
    *,
    app_path: Path,
    output_dir: Path,
    case_context_path: Path,
) -> dict[str, Any]:
    temp_dir = output_dir / ".streamlit_test_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    code = _streamlit_subprocess_code(app_path)
    env = os.environ.copy()
    env.update(
        {
            "TMP": str(temp_dir),
            "TEMP": str(temp_dir),
            "TMPDIR": str(temp_dir),
            "PROCUREWATCH_AGENT3_DEMO_DIR": str(output_dir),
            "PROCUREWATCH_AGENT4_CASE_CONTEXT": str(case_context_path),
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        }
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path.cwd(),
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
    except Exception as exc:
        return {
            "executed": True,
            "exceptions": [str(exc)],
            "metrics_count": None,
            "tabs_count": None,
            "title_count": None,
        }

    if completed.returncode != 0:
        return {
            "executed": True,
            "exceptions": [_trim_text(completed.stderr or completed.stdout)],
            "metrics_count": None,
            "tabs_count": None,
            "title_count": None,
        }
    return _parse_streamlit_subprocess_output(completed.stdout)


def _streamlit_subprocess_code(app_path: Path) -> str:
    return f"""
import json
import tempfile
from streamlit.testing.v1 import AppTest

tempfile.tempdir = tempfile.gettempdir()
app = AppTest.from_file({str(app_path)!r}, default_timeout=20).run(timeout=20)

def element_text(item):
    for attr in ("value", "message", "body"):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    return str(item)

print(json.dumps({{
    "executed": True,
    "exceptions": [element_text(item) for item in list(app.exception)],
    "metrics_count": len(app.metric),
    "tabs_count": len(app.tabs),
    "title_count": len(app.title),
}}))
"""


def _parse_streamlit_subprocess_output(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {
        "executed": True,
        "exceptions": [_trim_text(stdout) or "No se pudo leer salida JSON de AppTest."],
        "metrics_count": None,
        "tabs_count": None,
        "title_count": None,
    }


def _case_summary(payload: dict[str, Any]) -> dict[str, object]:
    case = _case_context(payload)
    return {
        "contract_key_canon": _case_contract_key(payload),
        "risk_score": _risk_score(payload),
        "red_flags_count": len(_red_flags(payload)),
        "agent3_metrics_count": len(case.get("agent3_metrics_used", {})),
        "evidences_count": len(case.get("evidences", [])),
        "citations_count": len(case.get("citations", [])),
    }


def _case_context(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("case_context")
    return value if isinstance(value, dict) else {}


def _case_contract_key(payload: dict[str, Any]) -> str:
    case = _case_context(payload)
    return str(payload.get("contract_key_canon") or case.get("contract_key_canon") or "")


def _risk_score(payload: dict[str, Any]) -> float | None:
    score = payload.get("agent2_score")
    if not isinstance(score, dict):
        score = _case_context(payload).get("agent2_score")
    if not isinstance(score, dict) or score.get("risk_score") is None:
        return None
    return float(score["risk_score"])


def _red_flags(payload: dict[str, Any]) -> list[str]:
    score = payload.get("agent2_score")
    if not isinstance(score, dict):
        score = _case_context(payload).get("agent2_score")
    if not isinstance(score, dict):
        return []
    flags = score.get("red_flags", [])
    return [str(flag) for flag in flags] if isinstance(flags, list) else []


def _integrated_report_path(integrated_report: dict[str, Any] | None, output_dir: Path) -> str:
    if isinstance(integrated_report, dict):
        artifacts = integrated_report.get("artifacts", {})
        if isinstance(artifacts, dict) and artifacts.get("integrated_report"):
            return str(artifacts["integrated_report"])
    return str(output_dir / "agent2_agent3_agent4_demo_report.json")


def _defense_commands(output_dir: Path, case_context_path: Path) -> dict[str, object]:
    return {
        "regenerate_demo": "python -m procurewatch.cli run-integrated-demo",
        "powershell_env": [
            f'$env:PROCUREWATCH_AGENT3_DEMO_DIR="{output_dir}"',
            f'$env:PROCUREWATCH_AGENT4_CASE_CONTEXT="{case_context_path}"',
        ],
        "open_dashboard": "streamlit run frontend/agent3_demo.py",
    }


def _check(name: str, passed: bool, details: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "details": details}


def _trim_text(text: str, *, max_chars: int = 1000) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


__all__ = [
    "DASHBOARD_APP_PATH",
    "DASHBOARD_CAPTURE_RECOMMENDATIONS",
    "DASHBOARD_VALIDATION_REPORT_FILENAME",
    "DASHBOARD_VALIDATION_SCHEMA_VERSION",
    "validate_dashboard_demo",
]
