from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_agent1_source_coverage_analysis(
    *,
    coverage: dict[str, Any],
    matching_diagnostics: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Write an analytical interpretation of source coverage and matching maturity."""
    report = {
        "dataset": "agent1_source_coverage_analysis",
        "schema_version": "0.1.0",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_key_counts": {
            "boe": int(coverage.get("boe_contract_keys", 0)),
            "place": int(coverage.get("place_contract_keys", 0)),
            "opentender": int(coverage.get("op_contract_keys", 0)),
            "universe": int(coverage.get("universe_contract_keys", 0)),
        },
        "exact_intersections": matching_diagnostics.get("exact_intersections", {}),
        "candidate_counts": matching_diagnostics.get("candidate_counts", {}),
        "candidate_class_counts": matching_diagnostics.get("candidate_class_counts", {}),
        "component_coverage": matching_diagnostics.get("component_coverage", {}),
        "interpretation": _build_interpretation(coverage, matching_diagnostics),
        "tfm_context": _build_tfm_context(coverage, matching_diagnostics),
        "institutional_readiness": _build_institutional_readiness(
            coverage,
            matching_diagnostics,
        ),
        "recommended_next_steps": _recommended_next_steps(coverage, matching_diagnostics),
        "warnings": matching_diagnostics.get("warnings", []),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "agent1_source_coverage_analysis.json"
    markdown_path = output_dir / "agent1_source_coverage_analysis.md"
    report["outputs"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_to_markdown(report), encoding="utf-8")
    return report


def _build_interpretation(
    coverage: dict[str, Any],
    matching_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    exact_intersections = matching_diagnostics.get("exact_intersections", {})
    total_exact = sum(int(value or 0) for value in exact_intersections.values())
    candidate_counts = matching_diagnostics.get("candidate_counts", {})
    total_candidates = sum(int(value or 0) for value in candidate_counts.values())
    has_exact_matches = total_exact > 0
    has_candidate_matches = total_candidates > 0

    if has_exact_matches:
        coverage_reading = (
            "Existe solapamiento exacto entre al menos dos fuentes, por lo que una parte del "
            "universo ya puede contrastarse de forma determinista."
        )
    else:
        coverage_reading = (
            "La cobertura actual es aditiva por fuente: el universo canonico conserva registros "
            "de BOE, PLACE y OpenTender, pero no acredita solapamiento exacto entre ellas."
        )

    if has_candidate_matches:
        matching_reading = (
            "Los candidatos aproximados son utiles como cola de revision, pero no deben usarse "
            "para fusionar contratos sin validacion adicional."
        )
    else:
        matching_reading = (
            "No hay candidatos aproximados con las claves diagnosticas actuales; el siguiente "
            "paso debe revisar disponibilidad de expediente, comprador, fecha, titulo e importe."
        )

    return {
        "coverage_reading": coverage_reading,
        "matching_reading": matching_reading,
        "robustness_impact": [
            "El scoring por fuente individual sigue siendo reproducible y trazable.",
            "La ausencia de intersecciones limita la triangulacion entre plataformas.",
            "Los historiales de comprador-proveedor pueden quedar fragmentados por fuente.",
            (
                "Los indicadores que dependen de consolidacion transversal deben tratarse "
                "como exploratorios."
            ),
        ],
        "methodological_contribution": (
            "El resultado muestra que integrar datos abiertos de contratacion no depende solo de "
            "llevarlos a un esquema comun: requiere una politica explicita de identificadores, "
            "normalizacion y validacion de matches."
        ),
        "safe_use_boundary": (
            "El pipeline puede alimentar analisis por fuente, scoring exploratorio y dashboard "
            "trazable; no debe presentarse como contraste institucional consolidado entre fuentes."
        ),
    }


def _build_tfm_context(
    coverage: dict[str, Any],
    matching_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    exact_intersections = matching_diagnostics.get("exact_intersections", {})
    total_exact = sum(int(value or 0) for value in exact_intersections.values())
    universe = int(coverage.get("universe_contract_keys", 0))
    return {
        "scope_table": [
            {
                "dimension": "Implementado",
                "status": "cerrado para el TFM",
                "reading": (
                    "Ingesta, normalizacion canonica, trazabilidad de fuente y diagnostico "
                    f"de cobertura sobre {universe} claves."
                ),
            },
            {
                "dimension": "Evaluado",
                "status": "medido con evidencias",
                "reading": (
                    "Cobertura por fuente, duplicados, intersecciones exactas y candidatos "
                    "aproximados de matching."
                ),
            },
            {
                "dimension": "Resultado critico",
                "status": "warning metodologico" if total_exact == 0 else "validacion parcial",
                "reading": (
                    "Las intersecciones exactas son 0; la cobertura es aditiva, no "
                    "transversal."
                    if total_exact == 0
                    else (
                        "Existen intersecciones exactas que permiten validacion "
                        "transversal parcial."
                    )
                ),
            },
            {
                "dimension": "Extension futura",
                "status": "fuera del cierre actual",
                "reading": (
                    "Calibrar una politica de matching con muestra manual y decisiones "
                    "auditables antes de fusionar fuentes."
                ),
            },
        ],
        "analytical_discussion": [
            (
                "Para un TFM, el valor del resultado no esta solo en obtener mas cobertura, "
                "sino en demostrar que cobertura por fuente y cobertura transversal son "
                "propiedades distintas."
            ),
            (
                "Con intersecciones exactas nulas, el sistema sigue siendo robusto para "
                "analisis reproducible por fuente, pero pierde capacidad de triangulacion "
                "entre portales."
            ),
            (
                "Forzar fusiones aproximadas mejoraria artificialmente algunos indicadores, "
                "pero reduciria trazabilidad y aumentaria riesgo de falsos matches."
            ),
        ],
        "institutional_implications": [
            "No se debe usar como registro consolidado unico sin validacion adicional.",
            "Los historiales comprador-proveedor pueden quedar fragmentados por fuente.",
            "Las metricas transversales deben marcarse como exploratorias.",
            "Una version institucional necesita reglas de matching revisables y auditables.",
        ],
    }


def _build_institutional_readiness(
    coverage: dict[str, Any],
    matching_diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    exact_intersections = matching_diagnostics.get("exact_intersections", {})
    candidate_counts = matching_diagnostics.get("candidate_counts", {})
    has_all_sources = all(
        int(coverage.get(key, 0)) > 0
        for key in ["boe_contract_keys", "place_contract_keys", "op_contract_keys"]
    )
    has_exact_matches = any(int(value or 0) > 0 for value in exact_intersections.values())
    has_candidates = any(int(value or 0) > 0 for value in candidate_counts.values())

    return [
        {
            "component": "ingesta_y_trazabilidad_por_fuente",
            "status": "green" if has_all_sources else "yellow",
            "evidence": (
                "Hay claves canonicas generadas para BOE, PLACE y OpenTender."
                if has_all_sources
                else "Falta al menos una fuente con claves canonicas en el reporte."
            ),
        },
        {
            "component": "cobertura_canonica_agent2",
            "status": "green" if int(coverage.get("universe_contract_keys", 0)) > 0 else "red",
            "evidence": (
                f"Universo canonico: {int(coverage.get('universe_contract_keys', 0))} claves."
            ),
        },
        {
            "component": "matching_transversal_validado",
            "status": "green" if has_exact_matches else "red",
            "evidence": (
                "Hay intersecciones exactas entre fuentes."
                if has_exact_matches
                else "Las intersecciones exactas entre fuentes son 0."
            ),
        },
        {
            "component": "cola_de_revision_de_matches",
            "status": "yellow" if has_candidates else "red",
            "evidence": (
                "Existen candidatos aproximados para revision no destructiva."
                if has_candidates
                else "No hay candidatos aproximados con las estrategias actuales."
            ),
        },
        {
            "component": "uso_institucional",
            "status": "yellow" if has_all_sources else "red",
            "evidence": (
                "Apto como prototipo de priorizacion y auditoria metodologica; no como "
                "registro institucional consolidado hasta validar matching transversal."
            ),
        },
    ]


def _recommended_next_steps(
    coverage: dict[str, Any],
    matching_diagnostics: dict[str, Any],
) -> list[str]:
    exact_intersections = matching_diagnostics.get("exact_intersections", {})
    has_exact_matches = any(int(value or 0) > 0 for value in exact_intersections.values())
    steps = [
        "Mantener separados los resultados por fuente hasta validar pares candidatos.",
        "Priorizar normalizacion de expediente, comprador, fecha, titulo, importe y CPV.",
        (
            "Crear una muestra revisada manualmente de pares candidato/no-match para "
            "calibrar umbrales."
        ),
        "Registrar la decision de matching como dato auditable antes de fusionar contratos.",
    ]
    if not has_exact_matches:
        steps.insert(
            0,
            (
                "No usar intersecciones entre fuentes como evidencia de contraste hasta "
                "resolver el matching."
            ),
        )
    if int(coverage.get("present_in_all", 0)) == 0:
        steps.append(
            "Tratar cualquier metrica transversal como exploratoria mientras present_in_all sea 0."
        )
    return steps


def _to_markdown(report: dict[str, Any]) -> str:
    counts = report["source_key_counts"]
    interpretation = report["interpretation"]
    tfm_context = report["tfm_context"]
    lines = [
        "# Diagnostico de cobertura entre fuentes",
        "",
        "## Resumen cuantitativo",
        "",
        "| Fuente | Claves canonicas |",
        "|---|---:|",
        f"| BOE | {counts['boe']} |",
        f"| PLACE | {counts['place']} |",
        f"| OpenTender | {counts['opentender']} |",
        f"| Universo | {counts['universe']} |",
        "",
        "## Intersecciones exactas",
        "",
        "| Par de fuentes | Intersecciones |",
        "|---|---:|",
    ]
    for pair, count in report["exact_intersections"].items():
        lines.append(f"| {pair} | {count} |")

    lines.extend(
        [
            "",
            "## Lectura en contexto de TFM",
            "",
            "| Dimension | Estado | Lectura |",
            "|---|---|---|",
        ]
    )
    for item in tfm_context["scope_table"]:
        lines.append(f"| {item['dimension']} | {item['status']} | {item['reading']} |")

    lines.extend(["", "## Discusion analitica", ""])
    for item in tfm_context["analytical_discussion"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Implicaciones para version institucional", ""])
    for item in tfm_context["institutional_implications"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Interpretacion",
            "",
            interpretation["coverage_reading"],
            "",
            interpretation["matching_reading"],
            "",
            f"**Aportacion metodologica:** {interpretation['methodological_contribution']}",
            "",
            f"**Limite de uso:** {interpretation['safe_use_boundary']}",
            "",
            "## Robustez",
            "",
        ]
    )
    for item in interpretation["robustness_impact"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Readiness institucional", "", "| Componente | Estado | Evidencia |"])
    lines.append("|---|---|---|")
    for item in report["institutional_readiness"]:
        lines.append(f"| {item['component']} | {item['status']} | {item['evidence']} |")

    lines.extend(["", "## Siguientes pasos", ""])
    for step in report["recommended_next_steps"]:
        lines.append(f"- {step}")
    lines.append("")
    return "\n".join(lines)


__all__ = ["build_agent1_source_coverage_analysis"]
