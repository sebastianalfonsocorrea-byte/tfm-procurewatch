from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True, slots=True)
class TemporalEvaluation:
    monthly: pd.DataFrame
    evaluated_contracts: int
    dated_contracts: int
    invalid_date_contracts: int
    invalid_score_contracts: int
    month_count: int


def load_temporal_evaluation(
    canonical_path: Path,
    scores_path: Path,
) -> TemporalEvaluation:
    """Load the evaluated Agent2 sample and aggregate contracts and risk by month."""
    for path in (canonical_path, scores_path):
        if not path.exists():
            raise FileNotFoundError(path)

    canonical = pd.read_parquet(canonical_path)
    scores = pd.read_parquet(scores_path)
    _require_columns(canonical, {"contract_key_canon", "publication_date"}, canonical_path)
    _require_columns(
        scores,
        {"contract_key_canon", "risk_score", "risk_level"},
        scores_path,
    )

    canonical = canonical[["contract_key_canon", "publication_date"]].copy()
    scores = scores[["contract_key_canon", "risk_score", "risk_level"]].copy()
    for frame, path in ((canonical, canonical_path), (scores, scores_path)):
        frame["contract_key_canon"] = (
            frame["contract_key_canon"].astype("string").fillna("").str.strip()
        )
        if frame["contract_key_canon"].eq("").any():
            raise ValueError(f"Empty contract_key_canon in {path}")
        if frame["contract_key_canon"].duplicated().any():
            raise ValueError(f"Duplicate contract_key_canon in {path}")

    merged = canonical.merge(
        scores,
        on="contract_key_canon",
        how="inner",
        validate="one_to_one",
    )
    merged["publication_date_parsed"] = pd.to_datetime(
        merged["publication_date"], errors="coerce"
    )
    merged["risk_score_parsed"] = pd.to_numeric(merged["risk_score"], errors="coerce")

    valid_dates = merged["publication_date_parsed"].notna()
    valid_scores = merged["risk_score_parsed"].notna()
    dated = merged.loc[valid_dates & valid_scores].copy()
    dated["month"] = dated["publication_date_parsed"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        dated.groupby("month", as_index=False)
        .agg(
            contracts=("contract_key_canon", "nunique"),
            mean_risk_score=("risk_score_parsed", "mean"),
        )
        .sort_values("month")
        .reset_index(drop=True)
    )
    monthly["mean_risk_score"] = monthly["mean_risk_score"].round(4)

    return TemporalEvaluation(
        monthly=monthly,
        evaluated_contracts=int(len(merged)),
        dated_contracts=int(valid_dates.sum()),
        invalid_date_contracts=int((~valid_dates).sum()),
        invalid_score_contracts=int((~valid_scores).sum()),
        month_count=int(monthly["month"].nunique()),
    )


def _require_columns(frame: pd.DataFrame, required: set[str], path: Path) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {sorted(missing)}")


__all__ = ["TemporalEvaluation", "load_temporal_evaluation"]
