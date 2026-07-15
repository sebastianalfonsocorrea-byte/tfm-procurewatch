from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

from .loader import validate_canonical_columns
from .schemas import GraphEdge, GraphNode, GraphTables

_CPV_RE = re.compile(r"\b\d{8}(?:-\d)?\b|\b\d{2,7}\b")
_NON_KEY_RE = re.compile(r"[^A-Z0-9]+")


def build_graph_tables(contracts: Any) -> GraphTables:
    records = _to_records(contracts)
    if not records:
        return GraphTables(nodes=[], edges=[], warnings=["No contracts received for Agent3 graph."])

    validate_canonical_columns(tuple(records[0].keys()))

    nodes_by_id: dict[str, GraphNode] = {}
    edges_by_id: dict[str, GraphEdge] = {}
    warnings: list[str] = []
    skipped_supplier_edges = 0
    skipped_cpv_edges = 0

    for record in records:
        contract_key = _clean(record.get("contract_key_canon"))
        source = _clean(record.get("source"))
        if not contract_key or not source:
            warnings.append("Skipped contract without contract_key_canon or source.")
            continue

        source_record_id = _optional_clean(record.get("source_record_id"))
        contract_node_id = f"contract:{contract_key}"
        nodes_by_id.setdefault(
            contract_node_id,
            GraphNode(
                node_id=contract_node_id,
                node_type="Contract",
                label=contract_key,
                attributes={
                    "contract_key_canon": contract_key,
                    "source": source,
                    "source_record_id": source_record_id,
                    "contract_title": _optional_clean(record.get("contract_title")),
                },
            ),
        )

        source_node_id = f"source:{_stable_key(source)}"
        nodes_by_id.setdefault(
            source_node_id,
            GraphNode(node_id=source_node_id, node_type="Source", label=source),
        )
        _add_edge(
            edges_by_id,
            source_node_id=contract_node_id,
            target_node_id=source_node_id,
            edge_type="FROM_SOURCE",
            contract_key_canon=contract_key,
            source=source,
            source_record_id=source_record_id,
        )

        buyer_node_id = _entity_node_id("buyer", record.get("buyer_id"), record.get("buyer_name"))
        buyer_label = _clean(record.get("buyer_name")) or buyer_node_id
        nodes_by_id.setdefault(
            buyer_node_id,
            GraphNode(
                node_id=buyer_node_id,
                node_type="Buyer",
                label=buyer_label,
                attributes={"buyer_id": _optional_clean(record.get("buyer_id"))},
            ),
        )
        _add_edge(
            edges_by_id,
            source_node_id=buyer_node_id,
            target_node_id=contract_node_id,
            edge_type="PUBLISHED",
            contract_key_canon=contract_key,
            source=source,
            source_record_id=source_record_id,
        )

        supplier_name = _clean(record.get("supplier_name"))
        if supplier_name:
            supplier_node_id = _entity_node_id(
                "supplier", record.get("supplier_id"), record.get("supplier_name")
            )
            nodes_by_id.setdefault(
                supplier_node_id,
                GraphNode(
                    node_id=supplier_node_id,
                    node_type="Supplier",
                    label=supplier_name,
                    attributes={"supplier_id": _optional_clean(record.get("supplier_id"))},
                ),
            )
            _add_edge(
                edges_by_id,
                source_node_id=contract_node_id,
                target_node_id=supplier_node_id,
                edge_type="AWARDED_TO",
                contract_key_canon=contract_key,
                source=source,
                source_record_id=source_record_id,
            )
        else:
            skipped_supplier_edges += 1

        cpv_codes = extract_cpv_codes(record.get("cpv_code_list"), record.get("cpv_codes_raw"))
        if not cpv_codes:
            skipped_cpv_edges += 1
        for cpv_code in cpv_codes:
            cpv_node_id = f"cpv:{cpv_code}"
            nodes_by_id.setdefault(
                cpv_node_id,
                GraphNode(node_id=cpv_node_id, node_type="CPV", label=cpv_code),
            )
            _add_edge(
                edges_by_id,
                source_node_id=contract_node_id,
                target_node_id=cpv_node_id,
                edge_type="HAS_CPV",
                contract_key_canon=contract_key,
                source=source,
                source_record_id=source_record_id,
            )

    if skipped_supplier_edges:
        warnings.append(f"Contracts without supplier relation: {skipped_supplier_edges}")
    if skipped_cpv_edges:
        warnings.append(f"Contracts without CPV relation: {skipped_cpv_edges}")

    return GraphTables(
        nodes=sorted(nodes_by_id.values(), key=lambda item: item.node_id),
        edges=sorted(edges_by_id.values(), key=lambda item: item.edge_id),
        warnings=warnings,
    )


def extract_cpv_codes(*values: object) -> list[str]:
    found: list[str] = []
    for value in values:
        text = _clean(value)
        if not text:
            continue
        for match in _CPV_RE.findall(text):
            code = match.split("-", maxsplit=1)[0]
            if code not in found:
                found.append(code)
    return found


def build_networkx_graph(graph_tables: GraphTables):
    try:
        import networkx as nx
    except ImportError as exc:
        raise RuntimeError("networkx is required to build the Agent3 graph object") from exc

    graph = nx.MultiDiGraph()
    for node in graph_tables.nodes:
        graph.add_node(node.node_id, node_type=node.node_type, label=node.label, **node.attributes)
    for edge in graph_tables.edges:
        graph.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            key=edge.edge_id,
            edge_type=edge.edge_type,
            contract_key_canon=edge.contract_key_canon,
            source=edge.source,
            source_record_id=edge.source_record_id,
            **edge.attributes,
        )
    return graph


def _add_edge(
    edges_by_id: dict[str, GraphEdge],
    *,
    source_node_id: str,
    target_node_id: str,
    edge_type: str,
    contract_key_canon: str,
    source: str,
    source_record_id: str | None,
) -> None:
    edge_id = f"{edge_type}:{source_node_id}->{target_node_id}:{contract_key_canon}"
    edges_by_id.setdefault(
        edge_id,
        GraphEdge(
            edge_id=edge_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            contract_key_canon=contract_key_canon,
            source=source,
            source_record_id=source_record_id,
        ),
    )


def _to_records(contracts: Any) -> list[Mapping[str, Any]]:
    if hasattr(contracts, "to_dict"):
        return contracts.to_dict("records")
    if isinstance(contracts, Iterable):
        return list(contracts)
    raise TypeError("contracts must be a pandas DataFrame or an iterable of mappings")


def _entity_node_id(prefix: str, identifier: object, name: object) -> str:
    strong_id = _clean(identifier)
    if strong_id:
        return f"{prefix}:{_stable_key(strong_id)}"
    return f"{prefix}:{_stable_key(_clean(name) or 'unknown')}"


def _stable_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    key = _NON_KEY_RE.sub("_", ascii_value.upper()).strip("_")
    return key or "UNKNOWN"


def _clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return str(value).strip()


def _optional_clean(value: object) -> str | None:
    cleaned = _clean(value)
    return cleaned or None
