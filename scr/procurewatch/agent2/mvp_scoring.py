from __future__ import annotations

from .mvp_rules import (
    awarded_above_estimate,
    missing_supplier,
    risky_procedure,
    temporal_anomaly,
)
from .schemas import Agent2Contract, Agent2Score

FLAG_WEIGHTS = {
    "RF-01": 15.0,
    "RF-02": 20.0,
    "RF-05": 25.0,
    "RF-06": 15.0,
}


def score_contract_mvp(
    contract: Agent2Contract,
    *,
    deviation_threshold: float = 0.10,
) -> Agent2Score:
    red_flags: list[str] = []
    evidence: dict[str, object] = {}

    if missing_supplier(contract):
        red_flags.append("RF-01")
        evidence["supplier_name"] = contract.supplier_name
    elif contract.supplier_count_in_tender == 1:
        red_flags.append("RF-01")
        evidence["source_tender_id"] = contract.source_tender_id
        evidence["supplier_count_in_tender"] = contract.supplier_count_in_tender
    if risky_procedure(contract):
        if contract.buyer_procedure_count is None or contract.buyer_procedure_count >= 2:
            red_flags.append("RF-02")
            evidence["procedure"] = contract.procedure
            evidence["buyer_procedure_count"] = contract.buyer_procedure_count
    if awarded_above_estimate(contract, deviation_threshold=deviation_threshold):
        red_flags.append("RF-05")
        evidence["estimated_value_eur"] = contract.estimated_value_eur
        evidence["awarded_value_eur"] = contract.awarded_value_eur
        if contract.estimated_value_eur and contract.estimated_value_eur > 0:
            evidence["deviation_ratio"] = (
                (contract.awarded_value_eur - contract.estimated_value_eur)
                / contract.estimated_value_eur
            )
    if temporal_anomaly(contract):
        red_flags.append("RF-06")
        evidence["publication_date"] = contract.publication_date
        evidence["award_date"] = contract.award_date
        evidence["resolution_days"] = contract.resolution_days

    return Agent2Score(
        contract_key_canon=contract.contract_key_canon,
        risk_score=min(sum(FLAG_WEIGHTS.get(flag, 0.0) for flag in red_flags), 100.0),
        red_flags=red_flags,
        evidence=evidence,
    )
