from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RF05_CODE = "RF-05"
RF05_RULE_VERSION = "1.0.0"
SCORE_VERSION = "1.0.0"
DEFAULT_DEVIATION_THRESHOLD = 0.10


def run_agent2(
    input_path: Path,
    output_dir: Path,
    deviation_threshold: float = DEFAULT_DEVIATION_THRESHOLD,
) -> dict[str, Any]:
    """Evaluate the first deterministic Agent2 rule over the Agent1 canonical dataset."""
    import pandas as pd

    if deviation_threshold < 0:
        raise ValueError("deviation_threshold must be greater than or equal to zero")
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    contracts = pd.read_parquet(input_path)
    required = {"contract_key_canon", "estimated_value_eur", "awarded_value_eur"}
    missing = required.difference(contracts.columns)
    if missing:
        raise ValueError(f"Missing Agent2 input columns: {sorted(missing)}")

    estimated = pd.to_numeric(contracts["estimated_value_eur"], errors="coerce")
    awarded = pd.to_numeric(contracts["awarded_value_eur"], errors="coerce")
    evaluable = estimated.gt(0) & awarded.notna()
    deviation_ratio = (awarded - estimated) / estimated
    activated = evaluable & deviation_ratio.gt(deviation_threshold)

    snapshot_id = _sha256(input_path)
    created_at = datetime.now(UTC).isoformat()
    activated_contract_ids = (
        contracts.loc[activated, "contract_key_canon"].astype(str).reset_index(drop=True)
    )
    activated_estimated = estimated[activated].reset_index(drop=True)
    activated_awarded = awarded[activated].reset_index(drop=True)
    activated_ratios = deviation_ratio[activated].reset_index(drop=True)

    flags = pd.DataFrame(
        {
            "risk_flag_id": [
                _stable_flag_id(contract_id, RF05_CODE, RF05_RULE_VERSION)
                for contract_id in activated_contract_ids
            ],
            "contract_key_canon": activated_contract_ids,
            "flag_code": RF05_CODE,
            "severity": "media",
            "confidence": 1.0,
            "evidence_fields": json.dumps(
                ["estimated_value_eur", "awarded_value_eur", "deviation_ratio"]
            ),
            "evidence_text": [
                (
                    f"Importe adjudicado {award:.2f} EUR frente a estimado {estimate:.2f} EUR; "
                    f"desviación {ratio:.2%}, superior al umbral {deviation_threshold:.2%}."
                )
                for estimate, award, ratio in zip(
                    activated_estimated,
                    activated_awarded,
                    activated_ratios,
                    strict=True,
                )
            ],
            "rule_version": RF05_RULE_VERSION,
            "created_at": created_at,
            "source_snapshot_id": snapshot_id,
        }
    )

    scores = pd.DataFrame(
        {
            "contract_key_canon": contracts["contract_key_canon"].astype(str),
            "risk_score": pd.Series(pd.NA, index=contracts.index, dtype="Float64"),
            "risk_level": pd.Series(pd.NA, index=contracts.index, dtype="string"),
            "flags_count": pd.Series(pd.NA, index=contracts.index, dtype="Int64"),
            "top_flags": pd.Series(pd.NA, index=contracts.index, dtype="object"),
            "evaluation_status": "no_evaluable",
            "score_version": SCORE_VERSION,
            "source_snapshot_id": snapshot_id,
        }
    )
    scores.loc[evaluable, "risk_score"] = 0.0
    scores.loc[evaluable, "risk_level"] = "bajo"
    scores.loc[evaluable, "flags_count"] = 0
    scores.loc[evaluable, "top_flags"] = "[]"
    scores.loc[evaluable, "evaluation_status"] = "evaluado"
    scores.loc[activated, "risk_score"] = 25.0
    scores.loc[activated, "risk_level"] = "medio"
    scores.loc[activated, "flags_count"] = 1
    scores.loc[activated, "top_flags"] = json.dumps([RF05_CODE])

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
        "evaluable_rows": int(evaluable.sum()),
        "not_evaluable_rows": int((~evaluable).sum()),
        "activated_flags": int(activated.sum()),
        "rules": {
            RF05_CODE: {
                "description": "Importe adjudicado superior al estimado.",
                "deviation_threshold": deviation_threshold,
                "rule_version": RF05_RULE_VERSION,
            }
        },
        "score_version": SCORE_VERSION,
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


def _stable_flag_id(contract_key: str, flag_code: str, rule_version: str) -> str:
    raw = f"{contract_key}|{flag_code}|{rule_version}".encode()
    return f"flag:{hashlib.sha256(raw).hexdigest()[:24]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
