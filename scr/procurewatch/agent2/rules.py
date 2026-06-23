from __future__ import annotations

from .schemas import Agent2Contract


def missing_supplier(contract: Agent2Contract) -> bool:
    return not contract.supplier_name.strip()


def awarded_above_estimate(contract: Agent2Contract) -> bool:
    if contract.estimated_value_eur is None or contract.awarded_value_eur is None:
        return False
    return contract.awarded_value_eur > contract.estimated_value_eur


def risky_procedure(contract: Agent2Contract) -> bool:
    procedure = contract.procedure.lower().strip()
    if not procedure:
        return False
    risky_terms = ("negociado", "restring", "menor")
    return any(term in procedure for term in risky_terms)
