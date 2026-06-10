from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Agent2Contract:
    contract_key_canon: str
    source: str
    source_record_id: str = ""
    source_dataset: str = ""
    buyer_name: str = ""
    buyer_id: str = ""
    supplier_name: str = ""
    supplier_id: str = ""
    contract_title: str = ""
    procedure: str = ""
    publication_date: str = ""
    award_date: str = ""
    estimated_value_eur: float | None = None
    awarded_value_eur: float | None = None
    cpv_codes_raw: str = ""
    cpv_code_list: str = ""
    source_file: str = ""


@dataclass(frozen=True)
class Agent2Score:
    contract_key_canon: str
    risk_score: float
    red_flags: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
