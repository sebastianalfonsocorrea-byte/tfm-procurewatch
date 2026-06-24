from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .mvp_scoring import FLAG_WEIGHTS, score_contract_mvp
from .schemas import Agent2Contract

RF01_CODE = "RF-01"
RF02_CODE = "RF-02"
RF03_CODE = "RF-03"
RF04_CODE = "RF-04"
RF05_CODE = "RF-05"
RF06_CODE = "RF-06"

RULE_VERSIONS = {
    RF01_CODE: "1.0.0",
    RF02_CODE: "1.0.0",
    RF03_CODE: "1.0.0",
    RF04_CODE: "1.0.0",
    RF05_CODE: "1.0.0",
    RF06_CODE: "1.0.0",
}

RULE_METADATA = {
    RF01_CODE: {
        "description": "Falta adjudicatario o identificador equivalente.",
        "weight": FLAG_WEIGHTS[RF01_CODE],
    },
    RF02_CODE: {
        "description": "Procedimiento de contratación sensible o de urgencia.",
        "weight": FLAG_WEIGHTS[RF02_CODE],
    },
    RF03_CODE: {
        "description": "Recurrencia comprador-proveedor observada en el canonico.",
        "weight": 20.0,
    },
    RF04_CODE: {
        "description": "Concentración de importe adjudicado en la pareja comprador-proveedor.",
        "weight": 20.0,
    },
    RF05_CODE: {
        "description": "Importe adjudicado superior al estimado.",
        "weight": FLAG_WEIGHTS[RF05_CODE],
    },
    RF06_CODE: {
        "description": "Patrón temporal anómalo entre publicación y adjudicación.",
        "weight": FLAG_WEIGHTS[RF06_CODE],
    },
}

SCORE_VERSION = "2.0.0"
DEFAULT_DEVIATION_THRESHOLD = 0.10
RECURRENCE_THRESHOLD = 2
CONCENTRATION_THRESHOLD = 0.50


def run_agent2_mvp(
    input_path: Path,
    output_dir: Path,
    deviation_threshold: float = DEFAULT_DEVIATION_THRESHOLD,
    agent3_features_path: Path | None = None,
) -> dict[str, Any]:
    """Execute the Agent 2 MVP over the canonical dataset produced by Agent 1."""
    import pandas as pd

    if deviation_threshold < 0:
        raise ValueError("deviation_threshold must be greater than or equal to zero")
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    contracts = pd.read_parquet(input_path).copy()
    required = {"contract_key_canon"}
    missing = required.difference(contracts.columns)
    if missing:
        raise ValueError(f"Missing Agent2 input columns: {sorted(missing)}")
    contracts["contract_key_canon"] = (
        contracts["contract_key_canon"].astype("string").fillna("").str.strip()
    )

    for column in [
        "buyer_name",
        "supplier_name",
        "procedure",
        "estimated_value_eur",
        "awarded_value_eur",
        "source",
        "source_record_id",
        "source_tender_id",
        "source_dataset",
        "buyer_id",
        "supplier_id",
        "contract_title",
        "publication_date",
        "award_date",
        "cpv_codes_raw",
        "cpv_code_list",
        "source_file",
    ]:
        if column not in contracts.columns:
            contracts[column] = (
                pd.NA
                if column not in {"buyer_name", "supplier_name", "procedure", "source_tender_id"}
                else ""
            )

    contracts["buyer_name"] = contracts["buyer_name"].astype("string").fillna("").str.strip()
    contracts["supplier_name"] = contracts["supplier_name"].astype("string").fillna("").str.strip()
    contracts["procedure"] = contracts["procedure"].astype("string").fillna("").str.strip()
    contracts["estimated_value_eur"] = pd.to_numeric(
        contracts["estimated_value_eur"],
        errors="coerce",
    )
    contracts["awarded_value_eur"] = pd.to_numeric(
        contracts["awarded_value_eur"],
        errors="coerce",
    )
    agent3_features, agent3_features_report = _load_agent3_features(
        agent3_features_path=agent3_features_path,
        contract_keys=contracts["contract_key_canon"],
    )
    if not agent3_features.empty:
        contracts = contracts.merge(agent3_features, on="contract_key_canon", how="left")
    for column in [
        "agent3_buyer_supplier_recurrence",
        "agent3_buyer_supplier_contract_share",
        "agent3_version",
    ]:
        if column not in contracts.columns:
            contracts[column] = pd.NA
    contracts["agent3_features_used"] = contracts[
        [
            "agent3_buyer_supplier_recurrence",
            "agent3_buyer_supplier_contract_share",
        ]
    ].notna().any(axis=1)
    contracts = contracts.reset_index(drop=True)
    agent3_features_report["matched_rows"] = int(contracts["agent3_features_used"].sum())
    if agent3_features_report["status"] == "used" and agent3_features_report["matched_rows"] == 0:
        agent3_features_report["status"] = "ignored"
        agent3_features_report["warnings"].append(
            "El fichero Agent3 existe, pero no tiene contratos coincidentes con la entrada Agent2."
        )

    snapshot_id = _sha256(input_path)
    created_at = datetime.now(UTC).isoformat()

    contracts["publication_date_parsed"] = pd.to_datetime(
        contracts["publication_date"],
        errors="coerce",
    )
    contracts["award_date_parsed"] = pd.to_datetime(contracts["award_date"], errors="coerce")
    contracts["resolution_days"] = (
        contracts["award_date_parsed"] - contracts["publication_date_parsed"]
    ).dt.days.astype("Int64")

    contracts["_supplier_key"] = contracts["supplier_name"].map(_normalize_key)
    contracts["_procedure_key"] = contracts["procedure"].map(_normalize_key)
    contracts["_buyer_key"] = contracts["buyer_name"].map(_normalize_key)
    tender_record_counts = (
        contracts[contracts["source_tender_id"].ne("")]
        .groupby("source_tender_id", dropna=False)
        .size()
    )
    tender_supplier_counts = (
        contracts[contracts["_supplier_key"].ne("") & contracts["source_tender_id"].ne("")]
        .groupby("source_tender_id", dropna=False)["_supplier_key"]
        .nunique(dropna=True)
    )
    buyer_procedure_counts = (
        contracts[contracts["_buyer_key"].ne("") & contracts["_procedure_key"].ne("")]
        .groupby(["_buyer_key", "_procedure_key"], dropna=False)
        .size()
    )

    base_scores: list[dict[str, Any]] = []
    flag_records: list[dict[str, Any]] = []
    rf05_evaluable_mask = (
        contracts["estimated_value_eur"].gt(0) & contracts["awarded_value_eur"].notna()
    )

    for index, record in enumerate(contracts.to_dict(orient="records")):
        contract = _record_to_contract(record)
        source_tender_id = _clean_text(record.get("source_tender_id"))
        buyer_key = _normalize_key(_clean_text(record.get("buyer_name")))
        procedure_key = _normalize_key(_clean_text(record.get("procedure")))
        tender_count = _int_or_none(tender_record_counts.get(source_tender_id, None))
        contract = Agent2Contract(
            **{
                **contract.__dict__,
                "source_tender_id": source_tender_id,
                "supplier_count_in_tender": _int_or_none(
                    tender_supplier_counts.get(source_tender_id, None)
                    if tender_count == 1
                    else None
                ),
                "buyer_procedure_count": _int_or_none(
                    buyer_procedure_counts.get((buyer_key, procedure_key), None)
                ),
                "resolution_days": _int_or_none(record.get("resolution_days")),
            }
        )
        score = score_contract_mvp(contract, deviation_threshold=deviation_threshold)
        active_flags = list(score.red_flags)
        base_scores.append(
            {
                "contract_key_canon": contract.contract_key_canon,
                "risk_score": min(float(score.risk_score), 100.0),
                "risk_level": _risk_level_from_score(score.risk_score),
                "flags_count": len(active_flags),
                "top_flags": json.dumps(active_flags, ensure_ascii=False),
                "evaluation_status": (
                    "evaluado" if bool(rf05_evaluable_mask.iloc[index]) else "no_evaluable"
                ),
                "score_version": SCORE_VERSION,
                "source_snapshot_id": snapshot_id,
                "agent3_features_used": bool(record.get("agent3_features_used", False)),
            }
        )
        for flag_code in active_flags:
            flag_records.append(
                _build_flag_record(
                    contract_key=contract.contract_key_canon,
                    flag_code=flag_code,
                    severity=_severity_for(flag_code),
                    confidence=1.0,
                    evidence_fields=list(score.evidence.keys()),
                    evidence_text=_evidence_text_for_row_local(
                        flag_code=flag_code,
                        contract=contract,
                        deviation_threshold=deviation_threshold,
                        evidence=score.evidence,
                    ),
                    rule_version=RULE_VERSIONS[flag_code],
                    created_at=created_at,
                    source_snapshot_id=snapshot_id,
                )
            )

    scores = pd.DataFrame(base_scores)

    pair_context = _build_contract_pair_context(contracts)
    for flag_code, threshold_check in [
        (RF03_CODE, pair_context["pair_count"].fillna(0) >= RECURRENCE_THRESHOLD),
        (
            RF04_CODE,
            (pair_context["pair_count"].fillna(0) >= RECURRENCE_THRESHOLD)
            & (pair_context["pair_share"].fillna(0.0) >= CONCENTRATION_THRESHOLD),
        ),
    ]:
        affected = pair_context[threshold_check]
        if affected.empty:
            continue
        scores, new_flag_records = _apply_contract_context_flag(
            scores=scores,
            contracts=contracts,
            affected=affected,
            flag_code=flag_code,
            created_at=created_at,
            snapshot_id=snapshot_id,
        )
        flag_records.extend(new_flag_records)

    flags = pd.DataFrame(
        flag_records,
        columns=[
            "risk_flag_id",
            "contract_key_canon",
            "flag_code",
            "severity",
            "confidence",
            "evidence_fields",
            "evidence_text",
            "rule_version",
            "created_at",
            "source_snapshot_id",
        ],
    )
    if flags.empty:
        flags = pd.DataFrame(
            columns=[
                "risk_flag_id",
                "contract_key_canon",
                "flag_code",
                "severity",
                "confidence",
                "evidence_fields",
                "evidence_text",
                "rule_version",
                "created_at",
                "source_snapshot_id",
            ]
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    flags_path = output_dir / "agent2_risk_flags.parquet"
    scores_path = output_dir / "agent2_risk_scores.parquet"
    report_path = output_dir / "agent2_run_report.json"
    flags.to_parquet(flags_path, index=False)
    scores.to_parquet(scores_path, index=False)

    report = {
        "input_path": str(input_path),
        "source_snapshot_id": snapshot_id,
        "rows": int(len(contracts)),
        "evaluable_rows": int(rf05_evaluable_mask.sum()),
        "not_evaluable_rows": int((~rf05_evaluable_mask).sum()),
        "activated_flags": int(len(flags)),
        "activated_contract_rows": int((scores["flags_count"] > 0).sum()),
        "rules": {
            **RULE_METADATA,
            RF05_CODE: {
                **RULE_METADATA[RF05_CODE],
                "deviation_threshold": deviation_threshold,
                "rule_version": RULE_VERSIONS[RF05_CODE],
            },
            RF06_CODE: {
                **RULE_METADATA[RF06_CODE],
                "rule_version": RULE_VERSIONS[RF06_CODE],
            },
        },
        "score_version": SCORE_VERSION,
        "agent3_features_path": agent3_features_report["path"],
        "agent3_features_status": agent3_features_report["status"],
        "agent3_features_rows": agent3_features_report["rows"],
        "agent3_features_matched_rows": agent3_features_report["matched_rows"],
        "agent3_features_warnings": agent3_features_report["warnings"],
        "flag_breakdown": flags.groupby("flag_code").size().to_dict() if not flags.empty else {},
        "risk_level_breakdown": scores.groupby("risk_level").size().to_dict(),
        "outputs": {
            "risk_flags": str(flags_path),
            "risk_scores": str(scores_path),
        },
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report["report_path"] = str(report_path)
    return report


def _load_agent3_features(
    *,
    agent3_features_path: Path | None,
    contract_keys: Any,
) -> tuple[Any, dict[str, Any]]:
    import pandas as pd

    empty = pd.DataFrame(
        columns=[
            "contract_key_canon",
            "agent3_buyer_supplier_recurrence",
            "agent3_buyer_supplier_contract_share",
            "agent3_version",
        ]
    )
    report: dict[str, Any] = {
        "path": str(agent3_features_path) if agent3_features_path is not None else None,
        "status": "ignored",
        "rows": 0,
        "matched_rows": 0,
        "warnings": [],
    }
    if agent3_features_path is None:
        return empty, report

    path = Path(agent3_features_path)
    if not path.exists():
        report["status"] = "missing"
        report["warnings"].append("No se encontro el fichero opcional de features Agent3.")
        return empty, report

    try:
        features = pd.read_parquet(path)
    except Exception as exc:
        report["warnings"].append(f"No se pudieron leer las features Agent3: {exc}")
        return empty, report

    report["rows"] = int(len(features))
    if "contract_key_canon" not in features.columns:
        report["warnings"].append("Las features Agent3 no contienen contract_key_canon.")
        return empty, report

    selected_columns = ["contract_key_canon"]
    optional_columns = [
        "buyer_supplier_recurrence",
        "buyer_supplier_contract_share",
        "agent3_version",
    ]
    selected_columns.extend(column for column in optional_columns if column in features.columns)
    selected = features[selected_columns].copy()
    selected["contract_key_canon"] = (
        selected["contract_key_canon"].astype("string").fillna("").str.strip()
    )
    selected = selected[selected["contract_key_canon"].ne("")]
    selected = selected.drop_duplicates("contract_key_canon", keep="first")

    rename_map = {
        "buyer_supplier_recurrence": "agent3_buyer_supplier_recurrence",
        "buyer_supplier_contract_share": "agent3_buyer_supplier_contract_share",
    }
    selected = selected.rename(columns=rename_map)
    for column in [
        "agent3_buyer_supplier_recurrence",
        "agent3_buyer_supplier_contract_share",
        "agent3_version",
    ]:
        if column not in selected.columns:
            selected[column] = pd.NA
    selected["agent3_buyer_supplier_recurrence"] = pd.to_numeric(
        selected["agent3_buyer_supplier_recurrence"],
        errors="coerce",
    )
    selected["agent3_buyer_supplier_contract_share"] = pd.to_numeric(
        selected["agent3_buyer_supplier_contract_share"],
        errors="coerce",
    )

    relevant_metrics = selected[
        [
            "agent3_buyer_supplier_recurrence",
            "agent3_buyer_supplier_contract_share",
        ]
    ].notna().any(axis=1)
    selected = selected[relevant_metrics]
    if selected.empty:
        report["warnings"].append("Las features Agent3 no contienen metricas RF-03/RF-04 utiles.")
        return empty, report

    input_keys = set(contract_keys.astype("string").fillna("").tolist())
    report["matched_rows"] = int(selected["contract_key_canon"].isin(input_keys).sum())
    report["status"] = "used" if report["matched_rows"] > 0 else "ignored"
    if report["matched_rows"] == 0:
        report["warnings"].append(
            "Las features Agent3 se leyeron correctamente, pero no coinciden con la entrada."
        )
    return selected, report


def _build_pair_context(contracts: Any) -> Any:
    pairs = contracts.copy()
    pairs["_buyer_key"] = pairs["buyer_name"].astype("string").fillna("").map(_normalize_key)
    pairs["_supplier_key"] = pairs["supplier_name"].astype("string").fillna("").map(_normalize_key)
    pairs["_pair_key"] = pairs["_buyer_key"] + "|" + pairs["_supplier_key"]

    pair_counts = (
        pairs[pairs["_buyer_key"].ne("") & pairs["_supplier_key"].ne("")]
        .groupby("_pair_key", dropna=False)
        .size()
        .rename("pair_count")
        .reset_index()
    )
    pair_awarded = (
        pairs[pairs["_buyer_key"].ne("") & pairs["_supplier_key"].ne("")]
        .groupby(["_buyer_key", "_supplier_key"], dropna=False)["awarded_value_eur"]
        .sum(min_count=1)
        .rename("pair_awarded")
        .reset_index()
    )
    buyer_totals = (
        pairs[pairs["_buyer_key"].ne("")]
        .groupby("_buyer_key", dropna=False)["awarded_value_eur"]
        .sum(min_count=1)
        .rename("buyer_total_awarded")
        .reset_index()
    )
    context = pair_awarded.merge(buyer_totals, on="_buyer_key", how="left")
    context["_pair_key"] = context["_buyer_key"] + "|" + context["_supplier_key"]
    context = context.merge(pair_counts, on="_pair_key", how="left")
    context["pair_share"] = context["pair_awarded"] / context["buyer_total_awarded"]
    context["pair_count"] = context["pair_count"].fillna(0).astype("Int64")
    return context


def _build_contract_pair_context(contracts: Any) -> Any:
    import pandas as pd

    context = contracts[
        [
            "contract_key_canon",
            "buyer_name",
            "supplier_name",
            "agent3_buyer_supplier_recurrence",
            "agent3_buyer_supplier_contract_share",
            "agent3_features_used",
        ]
    ].copy()
    context["_buyer_key"] = context["buyer_name"].astype("string").fillna("").map(_normalize_key)
    context["_supplier_key"] = (
        context["supplier_name"].astype("string").fillna("").map(_normalize_key)
    )
    pair_context = _build_pair_context(contracts).drop(columns=["_pair_key"], errors="ignore")
    context = context.merge(pair_context, on=["_buyer_key", "_supplier_key"], how="left")

    internal_pair_count = pd.to_numeric(context["pair_count"], errors="coerce")
    internal_pair_share = pd.to_numeric(context["pair_share"], errors="coerce")
    agent3_pair_count = pd.to_numeric(
        context["agent3_buyer_supplier_recurrence"],
        errors="coerce",
    )
    agent3_pair_share = pd.to_numeric(
        context["agent3_buyer_supplier_contract_share"],
        errors="coerce",
    )
    has_agent3_count = context["agent3_features_used"] & agent3_pair_count.notna()
    has_agent3_share = context["agent3_features_used"] & agent3_pair_share.notna()
    context["pair_count"] = internal_pair_count
    context["pair_share"] = internal_pair_share
    context.loc[has_agent3_count, "pair_count"] = agent3_pair_count[has_agent3_count]
    context.loc[has_agent3_share, "pair_share"] = agent3_pair_share[has_agent3_share]
    context["pair_metric_source"] = "agent2_internal"
    context.loc[has_agent3_count | has_agent3_share, "pair_metric_source"] = "agent3_features"
    return context


def _apply_contract_context_flag(
    *,
    scores: Any,
    contracts: Any,
    affected: Any,
    flag_code: str,
    created_at: str,
    snapshot_id: str,
) -> tuple[Any, list[dict[str, Any]]]:
    updated = scores.copy()
    new_records: list[dict[str, Any]] = []
    for _, row in affected.iterrows():
        contract_key = str(row["contract_key_canon"])
        row_indices = list(contracts.index[contracts["contract_key_canon"].eq(contract_key)])
        score_indices = list(updated.index[updated["contract_key_canon"].eq(contract_key)])
        if not row_indices or not score_indices:
            continue
        contract_index = row_indices[0]
        score_index = score_indices[0]
        current_flags = (
            json.loads(updated.at[score_index, "top_flags"])
            if updated.at[score_index, "top_flags"]
            else []
        )
        if flag_code in current_flags:
            continue
        current_flags.append(flag_code)
        updated.at[score_index, "flags_count"] = int(updated.at[score_index, "flags_count"]) + 1
        updated.at[score_index, "risk_score"] = min(
            float(updated.at[score_index, "risk_score"]) + RULE_METADATA[flag_code]["weight"],
            100.0,
        )
        updated.at[score_index, "risk_level"] = _risk_level_from_score(
            float(updated.at[score_index, "risk_score"])
        )
        updated.at[score_index, "top_flags"] = json.dumps(current_flags, ensure_ascii=False)
        evidence_fields = [
            "buyer_name",
            "supplier_name",
            "pair_count",
            "pair_share",
            "buyer_total_awarded",
            "pair_awarded",
            "pair_metric_source",
        ]
        if row.get("pair_metric_source") == "agent3_features":
            evidence_fields.extend(
                [
                    "agent3.buyer_supplier_recurrence",
                    "agent3.buyer_supplier_contract_share",
                ]
            )
        new_records.append(
            _build_flag_record(
                contract_key=contract_key,
                flag_code=flag_code,
                severity=_severity_for(flag_code),
                confidence=1.0,
                evidence_fields=evidence_fields,
                evidence_text=_evidence_text_for_batch(
                    flag_code=flag_code,
                    buyer_name=str(contracts.at[contract_index, "buyer_name"]),
                    supplier_name=str(contracts.at[contract_index, "supplier_name"]),
                    pair_count=_int_or_none(row.get("pair_count")) or 0,
                    pair_share=_coerce_float(row.get("pair_share")) or 0.0,
                    buyer_total_awarded=row.get("buyer_total_awarded"),
                    pair_awarded=row.get("pair_awarded"),
                    metric_source=str(row.get("pair_metric_source") or "agent2_internal"),
                ),
                rule_version=RULE_VERSIONS[flag_code],
                created_at=created_at,
                source_snapshot_id=snapshot_id,
            )
        )
    return updated, new_records


def _record_to_contract(record: dict[str, Any]) -> Agent2Contract:
    fields = {
        "contract_key_canon": str(record.get("contract_key_canon", "")),
        "source": str(record.get("source", "")),
        "source_record_id": str(record.get("source_record_id", "")),
        "source_tender_id": _clean_text(record.get("source_tender_id")),
        "source_dataset": str(record.get("source_dataset", "")),
        "buyer_name": _clean_text(record.get("buyer_name")),
        "buyer_id": str(record.get("buyer_id", "")),
        "supplier_name": _clean_text(record.get("supplier_name")),
        "supplier_id": str(record.get("supplier_id", "")),
        "contract_title": str(record.get("contract_title", "")),
        "procedure": _clean_text(record.get("procedure")),
        "publication_date": str(record.get("publication_date", "")),
        "award_date": str(record.get("award_date", "")),
        "estimated_value_eur": _coerce_float(record.get("estimated_value_eur")),
        "awarded_value_eur": _coerce_float(record.get("awarded_value_eur")),
        "cpv_codes_raw": str(record.get("cpv_codes_raw", "")),
        "cpv_code_list": record.get("cpv_code_list", ""),
        "source_file": str(record.get("source_file", "")),
    }
    return Agent2Contract(**fields)


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, float) and value != value:
            return None
        converted = float(value)
        if converted != converted:
            return None
        return converted
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        import pandas as pd

        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _int_or_none(value: Any) -> int | None:
    try:
        import pandas as pd

        if value is None or pd.isna(value):
            return None
    except Exception:
        if value is None:
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _severity_for(flag_code: str) -> str:
    return {
        RF01_CODE: "alta",
        RF02_CODE: "media",
        RF03_CODE: "media",
        RF04_CODE: "alta",
        RF05_CODE: "media",
    }.get(flag_code, "media")


def _risk_level_from_score(score: float) -> str:
    if score >= 75:
        return "critico"
    if score >= 50:
        return "alto"
    if score >= 25:
        return "medio"
    return "bajo"


def _normalize_key(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def _build_flag_record(
    *,
    contract_key: str,
    flag_code: str,
    severity: str,
    confidence: float,
    evidence_fields: list[str],
    evidence_text: str,
    rule_version: str,
    created_at: str,
    source_snapshot_id: str,
) -> dict[str, Any]:
    return {
        "risk_flag_id": _stable_flag_id(contract_key, flag_code, rule_version),
        "contract_key_canon": contract_key,
        "flag_code": flag_code,
        "severity": severity,
        "confidence": confidence,
        "evidence_fields": json.dumps(evidence_fields, ensure_ascii=False),
        "evidence_text": evidence_text,
        "rule_version": rule_version,
        "created_at": created_at,
        "source_snapshot_id": source_snapshot_id,
    }


def _evidence_text_for_row_local(
    *,
    flag_code: str,
    contract: Agent2Contract,
    deviation_threshold: float,
    evidence: dict[str, object],
) -> str:
    if flag_code == RF01_CODE:
        if contract.supplier_count_in_tender == 1:
            return (
                f"El expediente {contract.source_tender_id} solo muestra un adjudicatario "
                "en los registros disponibles."
            )
        return "No se ha identificado adjudicatario normalizado en el canonico."
    if flag_code == RF02_CODE:
        count = contract.buyer_procedure_count
        return (
            f"Procedimiento '{contract.procedure}' repetido {count} veces para el comprador "
            "en los registros disponibles."
        )
    if flag_code == RF05_CODE:
        estimate = float(evidence.get("estimated_value_eur") or 0.0)
        award = float(evidence.get("awarded_value_eur") or 0.0)
        ratio = float(evidence.get("deviation_ratio") or 0.0)
        return (
            f"Importe adjudicado {award:.2f} EUR frente a estimado {estimate:.2f} EUR; "
            f"desviación {ratio:.2%}, superior al umbral {deviation_threshold:.2%}."
        )
    if flag_code == RF06_CODE:
        return (
            f"Resolución en {contract.resolution_days} días entre publicación y adjudicación, "
            "fuera del patrón temporal esperado."
        )
    return "Señal determinista del MVP."


def _evidence_text_for_batch(
    *,
    flag_code: str,
    buyer_name: str,
    supplier_name: str,
    pair_count: int,
    pair_share: float,
    buyer_total_awarded: Any,
    pair_awarded: Any,
    metric_source: str = "agent2_internal",
) -> str:
    source_text = (
        "segun las features de Agent3"
        if metric_source == "agent3_features"
        else "en el canonico"
    )
    if flag_code == RF03_CODE:
        return (
            f"La pareja comprador-proveedor '{buyer_name}' / '{supplier_name}' se repite "
            f"{pair_count} veces {source_text}."
        )
    pair_awarded_text = _format_eur(pair_awarded)
    buyer_total_text = _format_eur(buyer_total_awarded)
    return (
        f"La pareja comprador-proveedor '{buyer_name}' / '{supplier_name}' concentra "
        f"{pair_awarded_text} sobre {buyer_total_text} del comprador "
        f"({pair_share:.2%}), {source_text}."
    )


def _format_eur(value: Any) -> str:
    converted = _coerce_float(value)
    if converted is None:
        return "importe no disponible"
    return f"{converted:.2f} EUR"


def _stable_flag_id(contract_key: str, flag_code: str, rule_version: str) -> str:
    raw = f"{contract_key}|{flag_code}|{rule_version}".encode()
    return f"flag:{hashlib.sha256(raw).hexdigest()[:24]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
