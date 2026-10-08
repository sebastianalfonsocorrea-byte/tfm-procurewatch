from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    node_type: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            **self.attributes,
        }


@dataclass(frozen=True, slots=True)
class GraphEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    contract_key_canon: str
    source: str
    source_record_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_type": self.edge_type,
            "contract_key_canon": self.contract_key_canon,
            "source": self.source,
            "source_record_id": self.source_record_id,
            **self.attributes,
        }


@dataclass(frozen=True, slots=True)
class GraphTables:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    warnings: list[str] = field(default_factory=list)

    def node_records(self) -> list[dict[str, Any]]:
        return [node.as_record() for node in self.nodes]

    def edge_records(self) -> list[dict[str, Any]]:
        return [edge.as_record() for edge in self.edges]


@dataclass(frozen=True, slots=True)
class ContractGraphMetrics:
    contract_key_canon: str
    source: str
    source_record_id: str | None
    buyer_supplier_recurrence: int
    buyer_degree: int
    supplier_degree: int
    supplier_contracts_count: int
    buyer_supplier_contract_share: float

    def as_record(self) -> dict[str, Any]:
        return {
            "contract_key_canon": self.contract_key_canon,
            "source": self.source,
            "source_record_id": self.source_record_id,
            "buyer_supplier_recurrence": self.buyer_supplier_recurrence,
            "buyer_degree": self.buyer_degree,
            "supplier_degree": self.supplier_degree,
            "supplier_contracts_count": self.supplier_contracts_count,
            "buyer_supplier_contract_share": self.buyer_supplier_contract_share,
        }
