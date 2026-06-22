from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schemas import ContractGraphMetrics, GraphTables

FEATURE_FAMILY = "agent3_graph_relation"
INTENDED_RED_FLAGS = ("RF-03", "RF-04", "AUX-NETWORK")
FEATURE_SCHEMA_VERSION = "0.1.0"


def build_agent2_feature_records(
    *,
    graph_tables: GraphTables,
    contract_metrics: list[ContractGraphMetrics],
    entity_metrics: list[Mapping[str, Any]],
    agent3_version: str,
    generated_at_utc: str,
) -> list[dict[str, Any]]:
    metrics_by_contract = {item.contract_key_canon: item.as_record() for item in contract_metrics}
    entity_metrics_by_node = {str(item["node_id"]): dict(item) for item in entity_metrics}
    relation_index = _build_relation_index(graph_tables)

    records = []
    for node in sorted(graph_tables.nodes, key=lambda item: item.node_id):
        if node.node_type != "Contract":
            continue

        contract_key = str(node.attributes.get("contract_key_canon") or node.label)
        contract_metrics_record = metrics_by_contract.get(contract_key, {})
        contract_entity = entity_metrics_by_node.get(node.node_id, {})
        buyer_node_id = relation_index["buyer_by_contract"].get(node.node_id)
        supplier_node_id = relation_index["supplier_by_contract"].get(node.node_id)
        buyer_entity = entity_metrics_by_node.get(buyer_node_id or "", {})
        supplier_entity = entity_metrics_by_node.get(supplier_node_id or "", {})

        records.append(
            {
                "contract_key_canon": contract_key,
                "source": node.attributes.get("source"),
                "source_record_id": node.attributes.get("source_record_id"),
                "buyer_supplier_recurrence": _metric_or_default(
                    contract_metrics_record,
                    "buyer_supplier_recurrence",
                    0,
                ),
                "buyer_supplier_contract_share": _metric_or_default(
                    contract_metrics_record,
                    "buyer_supplier_contract_share",
                    0.0,
                ),
                "buyer_degree": contract_metrics_record.get("buyer_degree"),
                "supplier_degree": contract_metrics_record.get("supplier_degree"),
                "supplier_contracts_count": contract_metrics_record.get(
                    "supplier_contracts_count"
                ),
                "contract_neighbor_count": contract_entity.get("neighbor_count", 0),
                "contract_degree_centrality": contract_entity.get("degree_centrality", 0.0),
                "contract_betweenness_centrality": contract_entity.get(
                    "betweenness_centrality",
                    0.0,
                ),
                "buyer_neighbor_count": buyer_entity.get("neighbor_count"),
                "buyer_degree_centrality": buyer_entity.get("degree_centrality"),
                "buyer_betweenness_centrality": buyer_entity.get("betweenness_centrality"),
                "supplier_neighbor_count": supplier_entity.get("neighbor_count"),
                "supplier_degree_centrality": supplier_entity.get("degree_centrality"),
                "supplier_betweenness_centrality": supplier_entity.get(
                    "betweenness_centrality"
                ),
                "component_id": contract_entity.get("component_id"),
                "component_size": contract_entity.get("component_size"),
                "community_id": contract_entity.get("community_id"),
                "community_size": contract_entity.get("community_size"),
                "cpv_count": len(relation_index["cpvs_by_contract"].get(node.node_id, set())),
                "has_supplier": supplier_node_id is not None,
                "agent3_version": agent3_version,
                "generated_at_utc": generated_at_utc,
            }
        )

    return sorted(records, key=lambda item: str(item["contract_key_canon"]))


def build_agent2_features_schema(
    *,
    agent3_version: str,
    generated_at_utc: str,
) -> dict[str, Any]:
    return {
        "dataset": "agent3_agent2_features",
        "schema_version": FEATURE_SCHEMA_VERSION,
        "agent3_version": agent3_version,
        "generated_at_utc": generated_at_utc,
        "primary_key": ["contract_key_canon"],
        "feature_family": FEATURE_FAMILY,
        "intended_red_flags": list(INTENDED_RED_FLAGS),
        "description": (
            "Features relacionales preparadas por Agent3 para scoring explicable futuro "
            "en Agent2. No declaran fraude."
        ),
        "limitations": [
            (
                "Los contratos sin proveedor mantienen has_supplier=false y metricas "
                "de proveedor nulas."
            ),
            "La calidad depende del matching actual de contract_key_canon y de IDs de entidades.",
            "Las centralidades son senales auxiliares, no evidencia concluyente.",
        ],
        "columns": _schema_columns(),
    }


def _build_relation_index(graph_tables: GraphTables) -> dict[str, dict[str, Any]]:
    buyer_by_contract: dict[str, str] = {}
    supplier_by_contract: dict[str, str] = {}
    cpvs_by_contract: dict[str, set[str]] = {}

    for edge in graph_tables.edges:
        if edge.edge_type == "PUBLISHED":
            buyer_by_contract[edge.target_node_id] = edge.source_node_id
        elif edge.edge_type == "AWARDED_TO":
            supplier_by_contract[edge.source_node_id] = edge.target_node_id
        elif edge.edge_type == "HAS_CPV":
            cpvs_by_contract.setdefault(edge.source_node_id, set()).add(edge.target_node_id)

    return {
        "buyer_by_contract": buyer_by_contract,
        "supplier_by_contract": supplier_by_contract,
        "cpvs_by_contract": cpvs_by_contract,
    }


def _metric_or_default(record: Mapping[str, Any], key: str, default: Any) -> Any:
    value = record.get(key)
    if value is None:
        return default
    return value


def _schema_columns() -> list[dict[str, Any]]:
    return [
        _column("contract_key_canon", "string", False, "Clave canonica de contrato."),
        _column("source", "string", True, "Fuente original del contrato."),
        _column("source_record_id", "string", True, "ID del registro en la fuente."),
        _column("buyer_supplier_recurrence", "integer", False, "Recurrencia comprador-proveedor."),
        _column(
            "buyer_supplier_contract_share",
            "float",
            False,
            "Peso del proveedor dentro de los contratos observados del comprador.",
        ),
        _column("buyer_degree", "integer", True, "Numero de proveedores asociados al comprador."),
        _column(
            "supplier_degree",
            "integer",
            True,
            "Numero de compradores asociados al proveedor.",
        ),
        _column(
            "supplier_contracts_count",
            "integer",
            True,
            "Contratos asociados al proveedor.",
        ),
        _column("contract_neighbor_count", "integer", False, "Vecinos directos del contrato."),
        _column("contract_degree_centrality", "float", False, "Centralidad de grado del contrato."),
        _column(
            "contract_betweenness_centrality",
            "float",
            False,
            "Betweenness centrality del contrato.",
        ),
        _column("buyer_neighbor_count", "integer", True, "Vecinos directos del comprador."),
        _column("buyer_degree_centrality", "float", True, "Centralidad de grado del comprador."),
        _column(
            "buyer_betweenness_centrality",
            "float",
            True,
            "Betweenness centrality del comprador.",
        ),
        _column("supplier_neighbor_count", "integer", True, "Vecinos directos del proveedor."),
        _column(
            "supplier_degree_centrality",
            "float",
            True,
            "Centralidad de grado del proveedor.",
        ),
        _column(
            "supplier_betweenness_centrality",
            "float",
            True,
            "Betweenness centrality del proveedor.",
        ),
        _column("component_id", "integer", True, "Componente conectada del contrato."),
        _column("component_size", "integer", True, "Tamano de la componente del contrato."),
        _column("community_id", "integer", True, "Comunidad Louvain del contrato."),
        _column("community_size", "integer", True, "Tamano de la comunidad del contrato."),
        _column("cpv_count", "integer", False, "Numero de CPV asociados al contrato."),
        _column("has_supplier", "boolean", False, "Indica si el contrato tiene proveedor."),
        _column("agent3_version", "string", False, "Version de Agent3 que genero la feature."),
        _column("generated_at_utc", "string", False, "Fecha UTC de generacion."),
    ]


def _column(name: str, data_type: str, nullable: bool, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "type": data_type,
        "nullable": nullable,
        "description": description,
    }
