from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .schemas import Agent2Contract
from .scoring import FLAG_WEIGHTS, score_contract

RF01_CODE = "RF-01"
RF02_CODE = "RF-02"
RF03_CODE = "RF-03"
RF04_CODE = "RF-04"
RF05_CODE = "RF-05"

RULE_VERSIONS = {
    RF01_CODE: "1.0.0",
    RF02_CODE: "1.0.0",
    RF03_CODE: "1.0.0",
    RF04_CODE: "1.0.0",
    RF05_CODE: "1.0.0",
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
}

SCORE_VERSION = "2.0.0"
DEFAULT_DEVIATION_THRESHOLD = 0.10
RECURRENCE_THRESHOLD = 2
CONCENTRATION_THRESHOLD = 0.50


def run_agent2(
    input_path: Path,
    output_dir: Path,
    deviation_threshold: float = DEFAULT_DEVIATION_THRESHOLD,
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

    base_scores: list[dict[str, Any]] = []
    flag_records: list[dict[str, Any]] = []
    rf05_evaluable_mask = contracts["estimated_value_eur"].gt(0) & contracts["awarded_value_eur"].notna()

    for index, record in enumerate(contracts.to_dict(orient="records")):
        contract = _record_to_contract(record)
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
        "rules": RULE_METADATA | {
            RF05_CODE: {
                **RULE_METADATA[RF05_CODE],
                "deviation_threshold": deviation_threshold,
                "rule_version": RULE_VERSIONS[RF05_CODE],
            }
        },
        "score_version": SCORE_VERSION,
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
        "source_dataset": str(record.get("source_dataset", "")),
        "buyer_name": str(record.get("buyer_name", "") or ""),
        "buyer_id": str(record.get("buyer_id", "")),
        "supplier_name": str(record.get("supplier_name", "") or ""),
        "supplier_id": str(record.get("supplier_id", "")),
        "contract_title": str(record.get("contract_title", "")),
        "procedure": str(record.get("procedure", "") or ""),
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
        return "No se ha identificado adjudicatario normalizado en el canonico."
    if flag_code == RF02_CODE:
        return f"Procedimiento '{contract.procedure}' clasificado como señal sensible del MVP."
    if flag_code == RF05_CODE:
        estimate = float(evidence.get("estimated_value_eur") or 0.0)
        award = float(evidence.get("awarded_value_eur") or 0.0)
        ratio = float(evidence.get("deviation_ratio") or 0.0)
        return (
            f"Importe adjudicado {award:.2f} EUR frente a estimado {estimate:.2f} EUR; "
            f"desviación {ratio:.2%}, superior al umbral {deviation_threshold:.2%}."
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
