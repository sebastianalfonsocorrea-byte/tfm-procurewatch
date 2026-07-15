from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from procurewatch.dashboard_temporal import load_temporal_evaluation


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    canonical_path = tmp_path / "canonical.parquet"
    scores_path = tmp_path / "scores.parquet"
    pd.DataFrame(
        [
            {"contract_key_canon": "C-1", "publication_date": "2024-01-05"},
            {"contract_key_canon": "C-2", "publication_date": "2024-01-20"},
            {"contract_key_canon": "C-3", "publication_date": "invalid"},
            {"contract_key_canon": "C-4", "publication_date": "2024-02-10"},
        ]
    ).to_parquet(canonical_path, index=False)
    pd.DataFrame(
        [
            {"contract_key_canon": "C-1", "risk_score": 10.0, "risk_level": "bajo"},
            {"contract_key_canon": "C-2", "risk_score": 30.0, "risk_level": "medio"},
            {"contract_key_canon": "C-3", "risk_score": 50.0, "risk_level": "medio"},
            {"contract_key_canon": "C-4", "risk_score": None, "risk_level": "bajo"},
        ]
    ).to_parquet(scores_path, index=False)
    return canonical_path, scores_path


def test_load_temporal_evaluation_aggregates_valid_months() -> None:
    canonical_path, scores_path = _write_inputs(_test_workspace("aggregate"))

    result = load_temporal_evaluation(canonical_path, scores_path)

    assert result.evaluated_contracts == 4
    assert result.dated_contracts == 3
    assert result.invalid_date_contracts == 1
    assert result.invalid_score_contracts == 1
    assert result.month_count == 1
    assert result.monthly["contracts"].tolist() == [2]
    assert result.monthly["mean_risk_score"].tolist() == [20.0]


def test_load_temporal_evaluation_rejects_missing_columns() -> None:
    canonical_path, scores_path = _write_inputs(_test_workspace("missing-columns"))
    pd.DataFrame([{"contract_key_canon": "C-1"}]).to_parquet(canonical_path, index=False)

    with pytest.raises(ValueError, match="publication_date"):
        load_temporal_evaluation(canonical_path, scores_path)


def test_load_temporal_evaluation_rejects_duplicate_keys() -> None:
    canonical_path, scores_path = _write_inputs(_test_workspace("duplicates"))
    scores = pd.read_parquet(scores_path)
    pd.concat([scores, scores.iloc[[0]]], ignore_index=True).to_parquet(scores_path, index=False)

    with pytest.raises(ValueError, match="Duplicate contract_key_canon"):
        load_temporal_evaluation(canonical_path, scores_path)


def test_load_temporal_evaluation_requires_both_artifacts() -> None:
    missing = _test_workspace("missing-artifacts") / "missing.parquet"

    with pytest.raises(FileNotFoundError):
        load_temporal_evaluation(missing, missing)


def _test_workspace(name: str) -> Path:
    path = Path("data/processed/dashboard_temporal_test_artifacts") / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path
