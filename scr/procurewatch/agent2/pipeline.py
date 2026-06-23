from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..db import write_agent2_risk_tables_to_postgres
from .comparison import build_agent2_model_comparison, evaluate_agent2_model_comparison
from .schemas import Agent2Contract
from .scoring import FLAG_WEIGHTS, score_contract

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
STABILITY_SAMPLE_SIZE = 25


def run_agent2(
    input_path: Path,
    output_dir: Path,
    deviation_threshold: float = DEFAULT_DEVIATION_THRESHOLD,
    postgres_dsn: str | None = None,
    write_postgres: bool = False,
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

    for column in [
        "buyer_name",
        "supplier_name",
        "procedure",
        "estimated_value_eur",
        "awarded_value_eur",
        "source",
        "source_record_id",
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
            contracts[column] = pd.NA if column not in {"buyer_name", "supplier_name", "procedure"} else ""

    contracts["buyer_name"] = contracts["buyer_name"].astype("string").fillna("").str.strip()
    contracts["supplier_name"] = contracts["supplier_name"].astype("string").fillna("").str.strip()
    contracts["procedure"] = contracts["procedure"].astype("string").fillna("").str.strip()
    contracts["estimated_value_eur"] = pd.to_numeric(contracts["estimated_value_eur"], errors="coerce")
    contracts["awarded_value_eur"] = pd.to_numeric(contracts["awarded_value_eur"], errors="coerce")

    snapshot_id = _sha256(input_path)
    created_at = datetime.now(UTC).isoformat()

    contracts["publication_date_parsed"] = pd.to_datetime(contracts["publication_date"], errors="coerce")
    contracts["award_date_parsed"] = pd.to_datetime(contracts["award_date"], errors="coerce")
    contracts["resolution_days"] = (
        contracts["award_date_parsed"] - contracts["publication_date_parsed"]
    ).dt.days.astype("Int64")

    contracts["_supplier_key"] = contracts["supplier_name"].map(_normalize_key)
    contracts["_procedure_key"] = contracts["procedure"].map(_normalize_key)
    contracts["_buyer_key"] = contracts["buyer_name"].map(_normalize_key)
    tender_record_counts = contracts[contracts["source_tender_id"].ne("")].groupby(
        "source_tender_id", dropna=False
    ).size()
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
    rf05_evaluable_mask = contracts["estimated_value_eur"].gt(0) & contracts["awarded_value_eur"].notna()

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
        score = score_contract(contract, deviation_threshold=deviation_threshold)
        active_flags = list(score.red_flags)
        base_scores.append(
            {
                "contract_key_canon": contract.contract_key_canon,
                "risk_score": min(float(score.risk_score), 100.0),
                "risk_level": _risk_level_from_score(score.risk_score),
                "flags_count": len(active_flags),
                "top_flags": json.dumps(active_flags, ensure_ascii=False),
                "evaluation_status": "evaluado" if bool(rf05_evaluable_mask.iloc[index]) else "no_evaluable",
                "score_version": SCORE_VERSION,
                "source_snapshot_id": snapshot_id,
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

    pair_context = _build_pair_context(contracts)
    for flag_code, threshold_check in [
        (RF03_CODE, pair_context["pair_count"] >= RECURRENCE_THRESHOLD),
        (
            RF04_CODE,
            (pair_context["pair_count"] >= RECURRENCE_THRESHOLD)
            & (pair_context["pair_share"] >= CONCENTRATION_THRESHOLD),
        ),
    ]:
        affected = pair_context[threshold_check]
        if affected.empty:
            continue
        scores, new_flag_records = _apply_batch_flag(
            scores=scores,
            contracts=contracts,
            affected=affected,
            flag_code=flag_code,
            created_at=created_at,
            snapshot_id=snapshot_id,
        )
        flag_records.extend(new_flag_records)

    supplier_summary = _build_supplier_summary(
        contracts=contracts,
        scores=scores,
        snapshot_id=snapshot_id,
    )
    model_comparison = build_agent2_model_comparison(
        contracts=contracts,
        scores=scores,
        deviation_threshold=deviation_threshold,
    )
    comparison_evaluation = evaluate_agent2_model_comparison(model_comparison)
    stability_check = _build_stability_check(
        contracts=contracts,
        deviation_threshold=deviation_threshold,
        sample_size=min(STABILITY_SAMPLE_SIZE, len(contracts)),
    )

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
    supplier_summary_path = output_dir / "agent2_supplier_risk_summary.parquet"
    comparison_path = output_dir / "agent2_model_comparison.parquet"
    report_path = output_dir / "agent2_run_report.json"
    flags.to_parquet(flags_path, index=False)
    scores.to_parquet(scores_path, index=False)
    supplier_summary.to_parquet(supplier_summary_path, index=False)
    model_comparison.to_parquet(comparison_path, index=False)

    postgres_write_report = None
    if write_postgres:
        if postgres_dsn is None:
            raise ValueError("postgres_dsn is required when write_postgres is enabled")
        postgres_write_report = write_agent2_risk_tables_to_postgres(
            risk_flags=flags,
            risk_scores=scores,
            supplier_risk_summary=supplier_summary,
            model_comparison=model_comparison,
            outputs=[
                {
                    "agent_name": "agent2",
                    "artifact_type": "risk_flags_parquet",
                    "artifact_path": str(flags_path),
                    "rows": int(len(flags)),
                    "source_snapshot_id": snapshot_id,
                    "created_at": created_at,
                    "payload_json": json.dumps(
                        {
                            "report_path": str(report_path),
                            "risk_flags": str(flags_path),
                            "risk_scores": str(scores_path),
                        },
                        ensure_ascii=False,
                    ),
                },
                {
                    "agent_name": "agent2",
                    "artifact_type": "risk_scores_parquet",
                    "artifact_path": str(scores_path),
                    "rows": int(len(scores)),
                    "source_snapshot_id": snapshot_id,
                    "created_at": created_at,
                    "payload_json": json.dumps(
                        {
                            "report_path": str(report_path),
                            "risk_flags": str(flags_path),
                            "risk_scores": str(scores_path),
                        },
                        ensure_ascii=False,
                    ),
                },
                {
                    "agent_name": "agent2",
                    "artifact_type": "supplier_risk_summary_parquet",
                    "artifact_path": str(supplier_summary_path),
                    "rows": int(len(supplier_summary)),
                    "source_snapshot_id": snapshot_id,
                    "created_at": created_at,
                    "payload_json": json.dumps(
                        {
                            "report_path": str(report_path),
                            "risk_flags": str(flags_path),
                            "risk_scores": str(scores_path),
                            "supplier_risk_summary": str(supplier_summary_path),
                        },
                        ensure_ascii=False,
                    ),
                },
                {
                    "agent_name": "agent2",
                    "artifact_type": "model_comparison_parquet",
                    "artifact_path": str(comparison_path),
                    "rows": int(len(model_comparison)),
                    "source_snapshot_id": snapshot_id,
                    "created_at": created_at,
                    "payload_json": json.dumps(
                        {
                            "report_path": str(report_path),
                            "model_comparison": str(comparison_path),
                        },
                        ensure_ascii=False,
                    ),
                },
                {
                    "agent_name": "agent2",
                    "artifact_type": "run_report_json",
                    "artifact_path": str(report_path),
                    "rows": 1,
                    "source_snapshot_id": snapshot_id,
                    "created_at": created_at,
                    "payload_json": json.dumps(
                        {
                            "report_path": str(report_path),
                            "risk_flags": str(flags_path),
                            "risk_scores": str(scores_path),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            postgres_dsn=postgres_dsn,
        )

    report = {
        "input_path": str(input_path),
        "source_snapshot_id": snapshot_id,
        "rows": int(len(contracts)),
        "evaluable_rows": int(rf05_evaluable_mask.sum()),
        "not_evaluable_rows": int((~rf05_evaluable_mask).sum()),
        "activated_flags": int(len(flags)),
        "activated_contract_rows": int((scores["flags_count"] > 0).sum()),
        "supplier_rows": int(len(supplier_summary)),
        "comparison_rows": int(len(model_comparison)),
        "comparison_evaluation": comparison_evaluation,
        "stability_check": stability_check,
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
        "flag_breakdown": flags.groupby("flag_code").size().to_dict() if not flags.empty else {},
        "risk_level_breakdown": scores.groupby("risk_level").size().to_dict(),
        "outputs": {
            "risk_flags": str(flags_path),
            "risk_scores": str(scores_path),
            "supplier_risk_summary": str(supplier_summary_path),
            "model_comparison": str(comparison_path),
        },
        "postgres_write": postgres_write_report,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report["report_path"] = str(report_path)
    return report


def _build_pair_context(contracts: Any) -> Any:
    import pandas as pd

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


def _build_stability_check(*, contracts: Any, deviation_threshold: float, sample_size: int) -> dict[str, Any]:
    import pandas as pd

    if sample_size <= 0 or contracts.empty:
        return {
            "sample_size": 0,
            "score_rows": 0,
            "model_rows": 0,
            "score_exact_match": True,
            "model_exact_match": True,
            "max_score_delta": 0.0,
            "mismatched_contracts": 0,
        }

    sample = contracts.sort_values("contract_key_canon").head(sample_size).copy()
    shuffled = sample.sample(frac=1.0, random_state=42).reset_index(drop=True)
    sample = sample.reset_index(drop=True)

    sample_scores = _score_contract_frame(sample, deviation_threshold=deviation_threshold)
    shuffled_scores = _score_contract_frame(shuffled, deviation_threshold=deviation_threshold)

    score_compare = sample_scores[["contract_key_canon", "risk_score", "top_flags"]].sort_values(
        "contract_key_canon"
    ).reset_index(drop=True)
    shuffled_compare = shuffled_scores[["contract_key_canon", "risk_score", "top_flags"]].sort_values(
        "contract_key_canon"
    ).reset_index(drop=True)

    merged = score_compare.merge(
        shuffled_compare,
        on="contract_key_canon",
        how="outer",
        suffixes=("_sample", "_shuffled"),
        indicator=True,
    )
    merged["risk_score_sample"] = pd.to_numeric(merged["risk_score_sample"], errors="coerce")
    merged["risk_score_shuffled"] = pd.to_numeric(merged["risk_score_shuffled"], errors="coerce")
    merged["top_flags_sample"] = merged["top_flags_sample"].astype("string")
    merged["top_flags_shuffled"] = merged["top_flags_shuffled"].astype("string")

    score_exact_match = bool(
        merged["_merge"].eq("both").all()
        and merged["risk_score_sample"].equals(merged["risk_score_shuffled"])
        and merged["top_flags_sample"].equals(merged["top_flags_shuffled"])
    )
    max_score_delta = float(
        (merged["risk_score_sample"] - merged["risk_score_shuffled"]).abs().fillna(0).max()
        if not merged.empty
        else 0.0
    )
    mismatched_contracts = int(
        (
            merged["_merge"].ne("both")
            | merged["risk_score_sample"].ne(merged["risk_score_shuffled"])
            | merged["top_flags_sample"].ne(merged["top_flags_shuffled"])
        ).sum()
    )

    sample_comparison = build_agent2_model_comparison(
        contracts=sample,
        scores=sample_scores,
        deviation_threshold=deviation_threshold,
    ).sort_values("contract_key_canon").reset_index(drop=True)
    shuffled_comparison = build_agent2_model_comparison(
        contracts=shuffled,
        scores=shuffled_scores,
        deviation_threshold=deviation_threshold,
    ).sort_values("contract_key_canon").reset_index(drop=True)

    model_columns = [
        "contract_key_canon",
        "rule_score",
        "rule_flags_count",
        "rule_positive",
        "iforest_anomaly_score",
        "iforest_anomaly_flag",
        "pu_probability",
        "pu_label",
        "agreement_iforest_rule",
        "agreement_pu_rule",
    ]
    model_exact_match = bool(
        sample_comparison[model_columns].equals(shuffled_comparison[model_columns])
    )

    return {
        "sample_size": int(sample_size),
        "score_rows": int(len(sample_scores)),
        "model_rows": int(len(sample_comparison)),
        "score_exact_match": score_exact_match,
        "model_exact_match": model_exact_match,
        "max_score_delta": round(max_score_delta, 6),
        "mismatched_contracts": mismatched_contracts,
    }


def _score_contract_frame(contracts: Any, *, deviation_threshold: float) -> Any:
    import pandas as pd

    frame = contracts.copy()
    for column in [
        "buyer_name",
        "supplier_name",
        "procedure",
        "estimated_value_eur",
        "awarded_value_eur",
        "source",
        "source_record_id",
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
        if column not in frame.columns:
            frame[column] = pd.NA if column not in {"buyer_name", "supplier_name", "procedure"} else ""
    frame["buyer_name"] = frame["buyer_name"].astype("string").fillna("").str.strip()
    frame["supplier_name"] = frame["supplier_name"].astype("string").fillna("").str.strip()
    frame["procedure"] = frame["procedure"].astype("string").fillna("").str.strip()
    frame["estimated_value_eur"] = pd.to_numeric(frame["estimated_value_eur"], errors="coerce")
    frame["awarded_value_eur"] = pd.to_numeric(frame["awarded_value_eur"], errors="coerce")
    frame["publication_date_parsed"] = pd.to_datetime(frame["publication_date"], errors="coerce")
    frame["award_date_parsed"] = pd.to_datetime(frame["award_date"], errors="coerce")
    frame["resolution_days"] = (
        frame["award_date_parsed"] - frame["publication_date_parsed"]
    ).dt.days.astype("Int64")
    frame["_supplier_key"] = frame["supplier_name"].map(_normalize_key)
    frame["_procedure_key"] = frame["procedure"].map(_normalize_key)
    frame["_buyer_key"] = frame["buyer_name"].map(_normalize_key)
    tender_record_counts = frame[frame["source_tender_id"].ne("")].groupby(
        "source_tender_id", dropna=False
    ).size()
    tender_supplier_counts = (
        frame[frame["_supplier_key"].ne("") & frame["source_tender_id"].ne("")]
        .groupby("source_tender_id", dropna=False)["_supplier_key"]
        .nunique(dropna=True)
    )
    buyer_procedure_counts = (
        frame[frame["_buyer_key"].ne("") & frame["_procedure_key"].ne("")]
        .groupby(["_buyer_key", "_procedure_key"], dropna=False)
        .size()
    )

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
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
        score = score_contract(contract, deviation_threshold=deviation_threshold)
        rows.append(
            {
                "contract_key_canon": contract.contract_key_canon,
                "risk_score": min(float(score.risk_score), 100.0),
                "flags_count": len(score.red_flags),
                "top_flags": json.dumps(list(score.red_flags), ensure_ascii=False),
            }
        )

    return pd.DataFrame(rows)


def _build_supplier_summary(*, contracts: Any, scores: Any, snapshot_id: str) -> Any:
    import pandas as pd

    combined = contracts[[
        "contract_key_canon",
        "buyer_name",
        "supplier_name",
        "supplier_id",
        "procedure",
        "awarded_value_eur",
    ]].copy()
    combined = combined.merge(
        scores[["contract_key_canon", "risk_score", "risk_level", "flags_count", "top_flags"]],
        on="contract_key_canon",
        how="left",
    )
    combined["supplier_key"] = combined["supplier_id"].astype("string").fillna("").str.strip()
    combined.loc[combined["supplier_key"].eq(""), "supplier_key"] = (
        combined["supplier_name"].astype("string").fillna("").map(_normalize_key)
    )
    combined = combined[combined["supplier_key"].ne("")]
    if combined.empty:
        return pd.DataFrame(
            columns=[
                "supplier_key",
                "supplier_id",
                "supplier_name",
                "total_contracts",
                "activated_contracts",
                "activated_contract_ratio",
                "total_importe_adjudicado",
                "organismos_distintos",
                "procedimientos_menores",
                "procedimientos_menores_ratio",
                "mean_risk_score",
                "max_risk_score",
                "score_riesgo_agregado",
                "risk_level",
                "red_flags_recurrentes",
                "score_version",
                "source_snapshot_id",
            ]
        )

    def _top_flags(value: Any) -> list[str]:
        try:
            return list(json.loads(value)) if value else []
        except Exception:
            return []

    combined["top_flags_list"] = combined["top_flags"].map(_top_flags)
    grouped = combined.groupby("supplier_key", dropna=False)
    records: list[dict[str, Any]] = []
    for supplier_key, frame in grouped:
        total_contracts = int(len(frame))
        activated_contracts = int((frame["flags_count"].fillna(0) > 0).sum())
        activated_contract_ratio = activated_contracts / total_contracts if total_contracts else 0.0
        mean_risk_score = float(frame["risk_score"].fillna(0).mean() if total_contracts else 0.0)
        max_risk_score = float(frame["risk_score"].fillna(0).max() if total_contracts else 0.0)
        aggregated_score = min(
            round(
                (mean_risk_score * 0.5)
                + (max_risk_score * 0.3)
                + (activated_contract_ratio * 100.0 * 0.2),
                2,
            ),
            100.0,
        )
        red_flags_counter: dict[str, int] = {}
        for flag_list in frame["top_flags_list"]:
            for flag in flag_list:
                red_flags_counter[flag] = red_flags_counter.get(flag, 0) + 1
        recurrent_flags = [
            flag for flag, count in sorted(red_flags_counter.items(), key=lambda item: (-item[1], item[0])) if count >= 2
        ]
        procedures_menores = int(
            frame["procedure"].astype("string").fillna("").map(_normalize_key).str.contains("MENOR", na=False).sum()
        )
        total_importe = float(frame["awarded_value_eur"].fillna(0).sum())
        organismos_distintos = int(frame["buyer_name"].astype("string").fillna("").nunique(dropna=True))
        procedures_menores_ratio = (
            procedures_menores / total_contracts if total_contracts else 0.0
        )
        supplier_id = str(frame["supplier_id"].dropna().iloc[0]) if frame["supplier_id"].notna().any() else ""
        supplier_name = str(frame["supplier_name"].dropna().iloc[0]) if frame["supplier_name"].notna().any() else ""
        records.append(
            {
                "supplier_key": supplier_key,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "total_contracts": total_contracts,
                "activated_contracts": activated_contracts,
                "activated_contract_ratio": round(activated_contract_ratio, 4),
                "total_importe_adjudicado": total_importe,
                "organismos_distintos": organismos_distintos,
                "procedimientos_menores": procedures_menores,
                "procedimientos_menores_ratio": procedures_menores_ratio,
                "mean_risk_score": round(mean_risk_score, 2),
                "max_risk_score": round(max_risk_score, 2),
                "score_riesgo_agregado": aggregated_score,
                "risk_level": _risk_level_from_score(aggregated_score),
                "red_flags_recurrentes": json.dumps(recurrent_flags, ensure_ascii=False),
                "score_version": SCORE_VERSION,
                "source_snapshot_id": snapshot_id,
            }
        )
    result = pd.DataFrame(records)
    result["source_snapshot_id"] = result["source_snapshot_id"].astype("string")
    return result


def _apply_batch_flag(
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
        buyer_key = str(row["_buyer_key"])
        supplier_key = str(row["_supplier_key"])
        mask = (
            contracts["buyer_name"].astype("string").fillna("").map(_normalize_key).eq(buyer_key)
            & contracts["supplier_name"].astype("string").fillna("").map(_normalize_key).eq(
                supplier_key
            )
        )
        row_indices = list(contracts.index[mask])
        if not row_indices:
            continue
        for index in row_indices:
            current_flags = json.loads(updated.at[index, "top_flags"]) if updated.at[index, "top_flags"] else []
            if flag_code in current_flags:
                continue
            current_flags.append(flag_code)
            updated.at[index, "flags_count"] = int(updated.at[index, "flags_count"]) + 1
            updated.at[index, "risk_score"] = min(
                float(updated.at[index, "risk_score"]) + RULE_METADATA[flag_code]["weight"],
                100.0,
            )
            updated.at[index, "risk_level"] = _risk_level_from_score(float(updated.at[index, "risk_score"]))
            updated.at[index, "top_flags"] = json.dumps(current_flags, ensure_ascii=False)
            new_records.append(
                _build_flag_record(
                    contract_key=str(contracts.at[index, "contract_key_canon"]),
                    flag_code=flag_code,
                    severity=_severity_for(flag_code),
                    confidence=1.0,
                    evidence_fields=[
                        "buyer_name",
                        "supplier_name",
                        "pair_count",
                        "pair_share",
                        "buyer_total_awarded",
                        "pair_awarded",
                    ],
                    evidence_text=_evidence_text_for_batch(
                        flag_code=flag_code,
                        buyer_name=str(contracts.at[index, "buyer_name"]),
                        supplier_name=str(contracts.at[index, "supplier_name"]),
                        pair_count=int(row["pair_count"]),
                        pair_share=float(row["pair_share"]),
                        buyer_total_awarded=row["buyer_total_awarded"],
                        pair_awarded=row["pair_awarded"],
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
) -> str:
    if flag_code == RF03_CODE:
        return (
            f"La pareja comprador-proveedor '{buyer_name}' / '{supplier_name}' se repite "
            f"{pair_count} veces en el canonico."
        )
    return (
        f"La pareja comprador-proveedor '{buyer_name}' / '{supplier_name}' concentra "
        f"{pair_awarded:.2f} EUR sobre {buyer_total_awarded:.2f} EUR del comprador "
        f"({pair_share:.2%})."
    )


def _stable_flag_id(contract_key: str, flag_code: str, rule_version: str) -> str:
    raw = f"{contract_key}|{flag_code}|{rule_version}".encode()
    return f"flag:{hashlib.sha256(raw).hexdigest()[:24]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
