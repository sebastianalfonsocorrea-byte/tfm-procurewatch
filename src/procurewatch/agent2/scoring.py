from __future__ import annotations

import hashlib
from dataclasses import asdict

from .rules import awarded_above_estimate, missing_supplier, risky_procedure
from .schemas import Agent2Contract, Agent2Score

AGENT2_SCORE_VERSION = "0.1.0"
RULE_VERSION = "agent2_rules_v1"

FLAG_METADATA: dict[str, dict[str, object]] = {
    "missing_supplier": {
        "flag_code": "DQ-01",
        "flag_name": "missing_supplier",
        "severity": "low",
        "confidence": 1.0,
        "evidence_fields": ["supplier_name", "supplier_id"],
    },
    "risky_procedure": {
        "flag_code": "RF-02",
        "flag_name": "risky_procedure",
        "severity": "medium",
        "confidence": 0.7,
        "evidence_fields": ["procedure"],
    },
    "awarded_above_estimate": {
        "flag_code": "RF-05",
        "flag_name": "awarded_above_estimate",
        "severity": "medium",
        "confidence": 0.8,
        "evidence_fields": ["estimated_value_eur", "awarded_value_eur"],
    },
}


def score_contract(contract: Agent2Contract) -> Agent2Score:
    red_flags: list[str] = []
    evidence: dict[str, object] = {}

    if missing_supplier(contract):
        red_flags.append("missing_supplier")
        evidence["supplier_name"] = contract.supplier_name
    if risky_procedure(contract):
        red_flags.append("risky_procedure")
        evidence["procedure"] = contract.procedure
    if awarded_above_estimate(contract):
        red_flags.append("awarded_above_estimate")
        evidence["estimated_value_eur"] = contract.estimated_value_eur
        evidence["awarded_value_eur"] = contract.awarded_value_eur

    risk_score = min(float(len(red_flags)) * 0.25, 1.0)
    return Agent2Score(
        contract_key_canon=contract.contract_key_canon,
        risk_score=risk_score,
        red_flags=red_flags,
        evidence=evidence,
        risk_level=risk_level_from_score(risk_score),
        flags_count=len(red_flags),
        top_flags=red_flags[:3],
        score_version=AGENT2_SCORE_VERSION,
    )


def risk_level_from_score(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def score_record(
    score: Agent2Score,
    contract: Agent2Contract,
    *,
    source_snapshot_id: str = "",
) -> dict[str, object]:
    record = asdict(score)
    record["source"] = contract.source
    record["source_record_id"] = contract.source_record_id
    record["source_snapshot_id"] = source_snapshot_id
    return record


def risk_flag_id(
    *,
    contract_key_canon: str,
    source: str,
    source_record_id: str,
    flag_code: str,
    rule_version: str = RULE_VERSION,
) -> str:
    raw = "|".join([contract_key_canon, source, source_record_id, flag_code, rule_version])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
