from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "procurewatch123"

NODE_LABELS = ("Buyer", "Supplier", "Contract", "CPV", "Source")
EDGE_TYPES = ("PUBLISHED", "AWARDED_TO", "HAS_CPV", "FROM_SOURCE")


def load_graph_to_neo4j(
    *,
    nodes_path: Path = Path("data/processed/agent3_nodes.parquet"),
    edges_path: Path = Path("data/processed/agent3_edges.parquet"),
    uri: str = DEFAULT_NEO4J_URI,
    user: str = DEFAULT_NEO4J_USER,
    password: str = DEFAULT_NEO4J_PASSWORD,
    database: str | None = None,
) -> dict[str, Any]:
    import pandas as pd
    from neo4j import GraphDatabase

    if not nodes_path.exists():
        raise FileNotFoundError(f"No existe fichero de nodos Agent3: {nodes_path}")
    if not edges_path.exists():
        raise FileNotFoundError(f"No existe fichero de aristas Agent3: {edges_path}")

    nodes = pd.read_parquet(nodes_path).to_dict("records")
    edges = pd.read_parquet(edges_path).to_dict("records")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        return load_graph_records_to_neo4j(
            driver=driver,
            nodes=nodes,
            edges=edges,
            database=database,
        )
    finally:
        driver.close()


def load_graph_records_to_neo4j(
    *,
    driver: Any,
    nodes: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any]],
    database: str | None = None,
    run_controls: bool = True,
) -> dict[str, Any]:
    node_batches = prepare_node_batches(nodes)
    edge_batches = prepare_edge_batches(edges)

    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        session.execute_write(_create_constraints)
        for label in NODE_LABELS:
            rows = node_batches.get(label, [])
            if rows:
                session.execute_write(_merge_nodes, label, rows)
        for edge_type in EDGE_TYPES:
            rows = edge_batches.get(edge_type, [])
            if rows:
                session.execute_write(_merge_edges, edge_type, rows)

        controls = run_control_queries(session) if run_controls else {}

    nodes_processed = sum(len(rows) for rows in node_batches.values())
    edges_processed = sum(len(rows) for rows in edge_batches.values())
    return {
        "nodes_processed": nodes_processed,
        "edges_processed": edges_processed,
        "nodes_by_type_input": dict(_batch_counts(node_batches)),
        "edges_by_type_input": dict(_batch_counts(edge_batches)),
        "controls": controls,
    }


def prepare_node_batches(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        node_id = _required_text(record, "node_id")
        label = _required_text(record, "node_type")
        _validate_node_label(label)
        properties = _clean_properties(record)
        properties["node_id"] = node_id
        properties["node_type"] = label
        batches[label].append({"node_id": node_id, "properties": properties})
    return {label: rows for label, rows in sorted(batches.items())}


def prepare_edge_batches(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        edge_id = _required_text(record, "edge_id")
        edge_type = _required_text(record, "edge_type")
        _validate_edge_type(edge_type)
        properties = _clean_properties(record)
        properties["edge_id"] = edge_id
        properties["edge_type"] = edge_type
        batches[edge_type].append(
            {
                "edge_id": edge_id,
                "source_node_id": _required_text(record, "source_node_id"),
                "target_node_id": _required_text(record, "target_node_id"),
                "properties": properties,
            }
        )
    return {edge_type: rows for edge_type, rows in sorted(batches.items())}


def run_control_queries(session: Any, *, contract_key_canon: str | None = None) -> dict[str, Any]:
    controls = {
        "nodes_by_type": session.execute_read(_count_nodes_by_type),
        "edges_by_type": session.execute_read(_count_edges_by_type),
        "top_buyers": session.execute_read(_top_buyers),
        "top_suppliers": session.execute_read(_top_suppliers),
    }
    if contract_key_canon:
        controls["contract_neighbors"] = session.execute_read(
            _contract_neighbors,
            contract_key_canon,
        )
    return controls


def _create_constraints(tx: Any) -> None:
    for label in NODE_LABELS:
        tx.run(
            f"""
            CREATE CONSTRAINT agent3_{label.lower()}_node_id IF NOT EXISTS
            FOR (n:{label})
            REQUIRE n.node_id IS UNIQUE
            """
        )


def _merge_nodes(tx: Any, label: str, rows: list[dict[str, Any]]) -> None:
    _validate_node_label(label)
    tx.run(
        f"""
        UNWIND $rows AS row
        MERGE (n:{label} {{node_id: row.node_id}})
        SET n += row.properties
        """,
        rows=rows,
    )


def _merge_edges(tx: Any, edge_type: str, rows: list[dict[str, Any]]) -> None:
    _validate_edge_type(edge_type)
    tx.run(
        f"""
        UNWIND $rows AS row
        MATCH (source {{node_id: row.source_node_id}})
        MATCH (target {{node_id: row.target_node_id}})
        MERGE (source)-[r:{edge_type} {{edge_id: row.edge_id}}]->(target)
        SET r += row.properties
        """,
        rows=rows,
    )


def _count_nodes_by_type(tx: Any) -> dict[str, int]:
    result = tx.run(
        """
        MATCH (n)
        WHERE n.node_id IS NOT NULL
        RETURN coalesce(n.node_type, labels(n)[0]) AS node_type, count(n) AS total
        ORDER BY node_type
        """
    )
    return {str(record["node_type"]): int(record["total"]) for record in result}


def _count_edges_by_type(tx: Any) -> dict[str, int]:
    result = tx.run(
        """
        MATCH ()-[r]->()
        WHERE r.edge_id IS NOT NULL
        RETURN type(r) AS edge_type, count(r) AS total
        ORDER BY edge_type
        """
    )
    return {str(record["edge_type"]): int(record["total"]) for record in result}


def _top_buyers(tx: Any, limit: int = 10) -> list[dict[str, Any]]:
    result = tx.run(
        """
        MATCH (buyer:Buyer)-[:PUBLISHED]->(contract:Contract)
        RETURN buyer.node_id AS node_id, buyer.label AS label, count(contract) AS contracts
        ORDER BY contracts DESC, label ASC
        LIMIT $limit
        """,
        limit=limit,
    )
    return [
        {
            "node_id": record["node_id"],
            "label": record["label"],
            "contracts": int(record["contracts"]),
        }
        for record in result
    ]


def _top_suppliers(tx: Any, limit: int = 10) -> list[dict[str, Any]]:
    result = tx.run(
        """
        MATCH (contract:Contract)-[:AWARDED_TO]->(supplier:Supplier)
        RETURN supplier.node_id AS node_id, supplier.label AS label, count(contract) AS contracts
        ORDER BY contracts DESC, label ASC
        LIMIT $limit
        """,
        limit=limit,
    )
    return [
        {
            "node_id": record["node_id"],
            "label": record["label"],
            "contracts": int(record["contracts"]),
        }
        for record in result
    ]


def _contract_neighbors(tx: Any, contract_key_canon: str) -> list[dict[str, Any]]:
    result = tx.run(
        """
        MATCH (contract:Contract {contract_key_canon: $contract_key_canon})-[rel]-(neighbor)
        RETURN
          type(rel) AS edge_type,
          neighbor.node_id AS node_id,
          neighbor.node_type AS node_type,
          neighbor.label AS label
        ORDER BY edge_type, node_type, label
        """,
        contract_key_canon=contract_key_canon,
    )
    return [
        {
            "edge_type": record["edge_type"],
            "node_id": record["node_id"],
            "node_type": record["node_type"],
            "label": record["label"],
        }
        for record in result
    ]


def _batch_counts(batches: Mapping[str, list[dict[str, Any]]]) -> Counter[str]:
    return Counter({key: len(rows) for key, rows in batches.items()})


def _required_text(record: Mapping[str, Any], key: str) -> str:
    value = _clean_value(record.get(key))
    if not isinstance(value, str) or not value:
        raise ValueError(f"Registro Agent3 sin valor obligatorio: {key}")
    return value


def _clean_properties(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: cleaned
        for key, value in record.items()
        if (cleaned := _clean_value(value)) is not None
    }


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    if hasattr(value, "item"):
        return _clean_value(value.item())
    if isinstance(value, Path):
        return str(value)
    return value


def _validate_node_label(label: str) -> None:
    if label not in NODE_LABELS:
        raise ValueError(f"Tipo de nodo Agent3 no permitido para Neo4j: {label}")


def _validate_edge_type(edge_type: str) -> None:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Tipo de arista Agent3 no permitido para Neo4j: {edge_type}")
