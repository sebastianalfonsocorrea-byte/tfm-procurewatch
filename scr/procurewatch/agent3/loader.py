from __future__ import annotations

from pathlib import Path

CANONICAL_REQUIRED_COLUMNS = (
    "contract_key_canon",
    "source",
    "buyer_name",
    "supplier_name",
    "cpv_codes_raw",
)


def validate_canonical_columns(columns: set[str] | list[str] | tuple[str, ...]) -> None:
    available = set(columns)
    missing = [column for column in CANONICAL_REQUIRED_COLUMNS if column not in available]
    if missing:
        raise ValueError(f"Missing canonical columns for Agent3: {', '.join(missing)}")


def load_canonical_contracts(path: Path):
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required to load Agent3 canonical parquet inputs") from exc

    contracts = pd.read_parquet(path)
    validate_canonical_columns(list(contracts.columns))
    return contracts
