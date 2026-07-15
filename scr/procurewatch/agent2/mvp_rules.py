from __future__ import annotations

from .schemas import Agent2Contract


def missing_supplier(contract: Agent2Contract) -> bool:
    return not contract.supplier_name.strip()


def risky_procedure(contract: Agent2Contract) -> bool:
    normalized = _normalize_text(contract.procedure)
    return any(marker in normalized for marker in ("MENOR", "EMERGENCIA", "NEGOCIADO"))


def temporal_anomaly(
    contract: Agent2Contract,
    *,
    temporal_days_threshold: float = 2.0,
) -> bool:
    if contract.resolution_days is None:
        return False
    if contract.resolution_days < 0:
        return True
    normalized = _normalize_text(contract.procedure)
    if "EMERGENCIA" in normalized:
        return False
    return contract.resolution_days <= temporal_days_threshold


def awarded_above_estimate(
    contract: Agent2Contract,
    *,
    deviation_threshold: float = 0.10,
) -> bool:
    if contract.estimated_value_eur is None or contract.awarded_value_eur is None:
        return False
    if contract.estimated_value_eur <= 0:
        return False
    deviation_ratio = (
        contract.awarded_value_eur - contract.estimated_value_eur
    ) / contract.estimated_value_eur
    return deviation_ratio > deviation_threshold


def _normalize_text(value: str) -> str:
    return value.strip().upper()
