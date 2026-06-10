from __future__ import annotations

from .rules import awarded_above_estimate, missing_supplier
from .schemas import Agent2Contract, Agent2Score


def score_contract(contract: Agent2Contract) -> Agent2Score:
    red_flags: list[str] = []
    evidence: dict[str, object] = {}

    if missing_supplier(contract):
        red_flags.append("missing_supplier")
    if awarded_above_estimate(contract):
        red_flags.append("awarded_above_estimate")
        evidence["estimated_value_eur"] = contract.estimated_value_eur
        evidence["awarded_value_eur"] = contract.awarded_value_eur

    return Agent2Score(
        contract_key_canon=contract.contract_key_canon,
        risk_score=min(float(len(red_flags)) * 0.25, 1.0),
        red_flags=red_flags,
        evidence=evidence,
    )
