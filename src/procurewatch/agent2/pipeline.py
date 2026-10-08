from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .schemas import Agent2Contract, Agent2RiskFlag, Agent2Score
from .scoring import FLAG_METADATA, RULE_VERSION, risk_flag_id, score_contract

DEFAULT_AGENT2_INPUT_PATH = Path("data/processed/agent2_contracts_canonical.parquet")
DEFAULT_AGENT2_OUTPUT_DIR = Path("data/processed")

SCORE_COLUMNS = [
    "contract_key_canon",
    "source",
    "source_record_id",
    "risk_score",
    "risk_level",
    "flags_count",
    "top_flags",
    "red_flags",
    "evidence",
    "score_version",
    "source_snapshot_id",
]

FLAG_COLUMNS = [
    "risk_flag_id",
    "contract_key_canon",
    "source",
    "source_record_id",
    "flag_code",
    "flag_name",
    "severity",
    "confidence",
    "evidence_fields",
    "evidence_text",
    "rule_version",
    "created_at_utc",
]


def run_agent2(
    *,
    input_path: Path = DEFAULT_AGENT2_INPUT_PATH,
    output_dir: Path = DEFAULT_AGENT2_OUTPUT_DIR,
    limit: int | None = None,
    source_snapshot_id: str | None = None,
) -> dict[str, Any]:
    import pandas as pd

    if not input_path.exists():
        raise FileNotFoundError(f"No existe canonico Agent2: {input_path}")

    generated_at_utc = datetime.now(UTC).isoformat()
    snapshot_id = source_snapshot_id or input_path.name
    output_dir.mkdir(parents=True, exist_ok=True)

    dataframe = pd.read_parquet(input_path)
    if limit is not None:
        dataframe = dataframe.head(limit)

    contracts = [contract_from_record(record) for record in dataframe.to_dict("records")]
    scores = [score_contract(contract) for contract in contracts]
    score_records = [
        score_output_record(score, contract, source_snapshot_id=snapshot_id)
        for score, contract in zip(scores, contracts, strict=True)
    ]
    flag_records = [
        asdict(flag)
        for score, contract in zip(scores, contracts, strict=True)
        for flag in build_risk_flags(
            contract,
            score,
            created_at_utc=generated_at_utc,
        )
    ]

    scores_df = pd.DataFrame(score_records, columns=SCORE_COLUMNS)
    flags_df = pd.DataFrame(flag_records, columns=FLAG_COLUMNS)

    outputs = {
        "risk_scores": output_dir / "agent2_risk_scores.parquet",
        "risk_flags": output_dir / "agent2_risk_flags.parquet",
        "risk_scores_preview": output_dir / "agent2_risk_scores_preview.csv",
        "risk_flags_preview": output_dir / "agent2_risk_flags_preview.csv",
        "risk_scores_schema": output_dir / "agent2_risk_scores_schema.json",
        "risk_flags_schema": output_dir / "agent2_risk_flags_schema.json",
        "report": output_dir / "agent2_scoring_report.json",
    }
    scores_df.to_parquet(outputs["risk_scores"], index=False)
    flags_df.to_parquet(outputs["risk_flags"], index=False)
    scores_df.head(500).to_csv(outputs["risk_scores_preview"], index=False, encoding="utf-8")
    flags_df.head(500).to_csv(outputs["risk_flags_preview"], index=False, encoding="utf-8")
    outputs["risk_scores_schema"].write_text(
        json.dumps(build_risk_scores_schema(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    outputs["risk_flags_schema"].write_text(
        json.dumps(build_risk_flags_schema(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report = {
        "agent": "agent2",
        "generated_at_utc": generated_at_utc,
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "source_snapshot_id": snapshot_id,
        "input_rows": int(len(dataframe)),
        "scores_rows": int(len(scores_df)),
        "flags_rows": int(len(flags_df)),
        "risk_level_counts": _value_counts(scores_df, "risk_level"),
        "flag_name_counts": _value_counts(flags_df, "flag_name"),
        "flag_code_counts": _value_counts(flags_df, "flag_code"),
        "outputs": {name: str(path) for name, path in outputs.items()},
        "limitations": [
            "Agent2 prioriza revision humana y no declara fraude.",
            "Las reglas v1 son intrafuente; no afirman contraste real entre fuentes.",
            "Las senales relacionales avanzadas quedan para consumo posterior de Agent3.",
        ],
    }
    outputs["report"].write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def contract_from_record(record: dict[str, object]) -> Agent2Contract:
    return Agent2Contract(
        contract_key_canon=_text(record, "contract_key_canon"),
        source=_text(record, "source"),
        source_record_id=_text(record, "source_record_id"),
        source_dataset=_text(record, "source_dataset"),
        buyer_name=_text(record, "buyer_name"),
        buyer_id=_text(record, "buyer_id"),
        supplier_name=_text(record, "supplier_name"),
        supplier_id=_text(record, "supplier_id"),
        contract_title=_text(record, "contract_title"),
        procedure=_text(record, "procedure"),
        publication_date=_text(record, "publication_date"),
        award_date=_text(record, "award_date"),
        estimated_value_eur=_float(record, "estimated_value_eur"),
        awarded_value_eur=_float(record, "awarded_value_eur"),
        cpv_codes_raw=_text(record, "cpv_codes_raw"),
        cpv_code_list=_text(record, "cpv_code_list"),
        source_file=_text(record, "source_file"),
    )


def build_risk_flags(
    contract: Agent2Contract,
    score: Agent2Score,
    *,
    created_at_utc: str,
) -> list[Agent2RiskFlag]:
    flags = []
    for flag_name in score.red_flags:
        metadata = FLAG_METADATA[flag_name]
        flag_code = str(metadata["flag_code"])
        flags.append(
            Agent2RiskFlag(
                risk_flag_id=risk_flag_id(
                    contract_key_canon=contract.contract_key_canon,
                    source=contract.source,
                    source_record_id=contract.source_record_id,
                    flag_code=flag_code,
                ),
                contract_key_canon=contract.contract_key_canon,
                source=contract.source,
                source_record_id=contract.source_record_id,
                flag_code=flag_code,
                flag_name=flag_name,
                severity=str(metadata["severity"]),
                confidence=float(metadata["confidence"]),
                evidence_fields=list(metadata["evidence_fields"]),
                evidence_text=_evidence_text(contract, flag_name),
                rule_version=RULE_VERSION,
                created_at_utc=created_at_utc,
            )
        )
    return flags


def score_output_record(
    score: Agent2Score,
    contract: Agent2Contract,
    *,
    source_snapshot_id: str,
) -> dict[str, object]:
    return {
        "contract_key_canon": score.contract_key_canon,
        "source": contract.source,
        "source_record_id": contract.source_record_id,
        "risk_score": score.risk_score,
        "risk_level": score.risk_level,
        "flags_count": score.flags_count,
        "top_flags": json.dumps(score.top_flags, ensure_ascii=False),
        "red_flags": json.dumps(score.red_flags, ensure_ascii=False),
        "evidence": json.dumps(score.evidence, ensure_ascii=False),
        "score_version": score.score_version,
        "source_snapshot_id": source_snapshot_id,
    }


def build_risk_scores_schema() -> dict[str, Any]:
    return {
        "dataset": "agent2_risk_scores",
        "schema_version": "0.1.0",
        "primary_key": ["contract_key_canon", "source", "source_record_id"],
        "columns": SCORE_COLUMNS,
        "description": "Scoring determinista v1 de Agent2 para priorizar revision humana.",
    }


def build_risk_flags_schema() -> dict[str, Any]:
    return {
        "dataset": "agent2_risk_flags",
        "schema_version": "0.1.0",
        "primary_key": ["risk_flag_id"],
        "columns": FLAG_COLUMNS,
        "description": "Red flags trazables v1 de Agent2. No declaran fraude.",
    }


def _evidence_text(contract: Agent2Contract, flag_name: str) -> str:
    if flag_name == "missing_supplier":
        return "No consta supplier_name/supplier_id en el contrato canonico."
    if flag_name == "risky_procedure":
        return f"Procedimiento potencialmente sensible detectado: {contract.procedure}."
    if flag_name == "awarded_above_estimate":
        return (
            f"Importe adjudicado {contract.awarded_value_eur} supera el estimado "
            f"{contract.estimated_value_eur}."
        )
    return "Senal de riesgo detectada por regla determinista."


def _value_counts(dataframe: Any, column: str) -> dict[str, int]:
    if dataframe.empty or column not in dataframe.columns:
        return {}
    return {str(key): int(value) for key, value in dataframe[column].value_counts().items()}


def _text(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if _is_missing(value):
        return ""
    return str(value)


def _float(record: dict[str, object], key: str) -> float | None:
    value = record.get(key)
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


__all__ = [
    "DEFAULT_AGENT2_INPUT_PATH",
    "DEFAULT_AGENT2_OUTPUT_DIR",
    "build_risk_flags",
    "build_risk_flags_schema",
    "build_risk_scores_schema",
    "contract_from_record",
    "run_agent2",
    "score_output_record",
]
