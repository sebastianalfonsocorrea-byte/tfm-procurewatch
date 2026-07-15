from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from .schemas import ContractGraphMetrics


def compute_contract_graph_metrics(contracts: Any) -> list[ContractGraphMetrics]:
    records = _to_records(contracts)
    valid_records = [
        record
        for record in records
        if _clean(record.get("contract_key_canon"))
        and _clean(record.get("buyer_name"))
        and _clean(record.get("supplier_name"))
    ]
    if not valid_records:
        return []

    pair_counts: Counter[tuple[str, str]] = Counter()
    supplier_counts: Counter[str] = Counter()
    buyer_contract_counts: Counter[str] = Counter()
    buyer_suppliers: dict[str, set[str]] = defaultdict(set)
    supplier_buyers: dict[str, set[str]] = defaultdict(set)

    for record in valid_records:
        buyer_key = _entity_key(record.get("buyer_id"), record.get("buyer_name"))
        supplier_key = _entity_key(record.get("supplier_id"), record.get("supplier_name"))
        pair_counts[(buyer_key, supplier_key)] += 1
        supplier_counts[supplier_key] += 1
        buyer_contract_counts[buyer_key] += 1
        buyer_suppliers[buyer_key].add(supplier_key)
        supplier_buyers[supplier_key].add(buyer_key)

    metrics: list[ContractGraphMetrics] = []
    seen_contracts: set[str] = set()
    for record in valid_records:
        contract_key = _clean(record.get("contract_key_canon"))
        if contract_key in seen_contracts:
            continue
        seen_contracts.add(contract_key)

        buyer_key = _entity_key(record.get("buyer_id"), record.get("buyer_name"))
        supplier_key = _entity_key(record.get("supplier_id"), record.get("supplier_name"))
        recurrence = pair_counts[(buyer_key, supplier_key)]
        buyer_total = buyer_contract_counts[buyer_key]
        share = recurrence / buyer_total if buyer_total else 0.0
        metrics.append(
            ContractGraphMetrics(
                contract_key_canon=contract_key,
                source=_clean(record.get("source")),
                source_record_id=_optional_clean(record.get("source_record_id")),
                buyer_supplier_recurrence=recurrence,
                buyer_degree=len(buyer_suppliers[buyer_key]),
                supplier_degree=len(supplier_buyers[supplier_key]),
                supplier_contracts_count=supplier_counts[supplier_key],
                buyer_supplier_contract_share=round(share, 6),
            )
        )

    return sorted(metrics, key=lambda item: item.contract_key_canon)


def _to_records(contracts: Any) -> list[Mapping[str, Any]]:
    if hasattr(contracts, "to_dict"):
        return contracts.to_dict("records")
    if isinstance(contracts, Iterable):
        return list(contracts)
    raise TypeError("contracts must be a pandas DataFrame or an iterable of mappings")


def _entity_key(identifier: object, name: object) -> str:
    strong_id = _clean(identifier)
    return strong_id.upper() if strong_id else _clean(name).upper()


def _clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return str(value).strip()


def _optional_clean(value: object) -> str | None:
    cleaned = _clean(value)
    return cleaned or None
