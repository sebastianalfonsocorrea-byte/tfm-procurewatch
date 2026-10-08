from __future__ import annotations

from .rules import awarded_above_estimate, missing_supplier, risky_procedure, temporal_anomaly
from .schemas import Agent2Contract, Agent2Score

SCORE_VERSION = "3.0.0"

DQ01_CODE = "DQ-01"
RF01_CODE = "RF-01"
RF02_CODE = "RF-02"
RF03_CODE = "RF-03"
RF04_CODE = "RF-04"
RF05_CODE = "RF-05"
RF06_CODE = "RF-06"

RULE_CODES = [RF01_CODE, RF02_CODE, RF03_CODE, RF04_CODE, RF05_CODE, RF06_CODE]
DATA_QUALITY_CODES = [DQ01_CODE]

# Weights of the risk rules on a 0-100 scale. They add up to 115, so the score is capped at
# 100. Data quality signals (DQ-*) are reported alongside the score but never weighted.
FLAG_WEIGHTS = {
    RF01_CODE: 15.0,
    RF02_CODE: 20.0,
    RF03_CODE: 20.0,
    RF04_CODE: 20.0,
    RF05_CODE: 25.0,
    RF06_CODE: 15.0,
}

FLAG_DESCRIPTIONS = {
    DQ01_CODE: "Falta adjudicatario o identificador equivalente (calidad del dato).",
    RF01_CODE: "Expediente con un único adjudicatario en los registros disponibles.",
    RF02_CODE: "Procedimiento de contratación sensible o de urgencia.",
    RF03_CODE: "Recurrencia comprador-proveedor observada en el canónico.",
    RF04_CODE: "Concentración de importe adjudicado en la pareja comprador-proveedor.",
    RF05_CODE: "Importe adjudicado superior al estimado.",
    RF06_CODE: "Patrón temporal anómalo entre publicación y adjudicación.",
}

FLAG_SEVERITIES = {
    DQ01_CODE: "calidad_dato",
    RF01_CODE: "alta",
    RF02_CODE: "media",
    RF03_CODE: "media",
    RF04_CODE: "alta",
    RF05_CODE: "media",
    RF06_CODE: "media",
}

RISK_LEVELS = ("bajo", "medio", "alto", "critico")


def score_contract(
    contract: Agent2Contract,
    *,
    deviation_threshold: float = 0.10,
    temporal_days_threshold: float = 2.0,
) -> Agent2Score:
    """Score the contract-local rules (RF-01, RF-02, RF-05, RF-06) plus data quality.

    RF-03/RF-04 need the whole batch (buyer-supplier pairs) and are added by run_agent2.
    """
    red_flags: list[str] = []
    data_quality_flags: list[str] = []
    evidence: dict[str, object] = {}

    if missing_supplier(contract):
        data_quality_flags.append(DQ01_CODE)
        evidence["supplier_name"] = contract.supplier_name
    elif contract.supplier_count_in_tender == 1:
        red_flags.append(RF01_CODE)
        evidence["source_tender_id"] = contract.source_tender_id
        evidence["supplier_count_in_tender"] = contract.supplier_count_in_tender
    if risky_procedure(contract):
        if contract.buyer_procedure_count is None or contract.buyer_procedure_count >= 2:
            red_flags.append(RF02_CODE)
            evidence["procedure"] = contract.procedure
            evidence["buyer_procedure_count"] = contract.buyer_procedure_count
    if awarded_above_estimate(contract, deviation_threshold=deviation_threshold):
        red_flags.append(RF05_CODE)
        evidence["estimated_value_eur"] = contract.estimated_value_eur
        evidence["awarded_value_eur"] = contract.awarded_value_eur
        if contract.estimated_value_eur and contract.estimated_value_eur > 0:
            evidence["deviation_ratio"] = (
                contract.awarded_value_eur - contract.estimated_value_eur
            ) / contract.estimated_value_eur
    if temporal_anomaly(contract, temporal_days_threshold=temporal_days_threshold):
        red_flags.append(RF06_CODE)
        evidence["publication_date"] = contract.publication_date
        evidence["award_date"] = contract.award_date
        evidence["resolution_days"] = contract.resolution_days

    risk_score = score_from_flags(red_flags)
    return Agent2Score(
        contract_key_canon=contract.contract_key_canon,
        risk_score=risk_score,
        red_flags=red_flags,
        evidence=evidence,
        risk_level=risk_level_from_score(risk_score),
        flags_count=len(red_flags),
        top_flags=red_flags[:3],
        score_version=SCORE_VERSION,
        data_quality_flags=data_quality_flags,
    )


def score_from_flags(flags: list[str]) -> float:
    return min(sum(FLAG_WEIGHTS.get(flag, 0.0) for flag in flags), 100.0)


def risk_level_from_score(score: float) -> str:
    if score >= 75:
        return "critico"
    if score >= 50:
        return "alto"
    if score >= 25:
        return "medio"
    return "bajo"
