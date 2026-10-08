from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

AGENT3_DEMO_ARTIFACTS = {
    "nodes": "agent3_nodes.parquet",
    "edges": "agent3_edges.parquet",
    "entity_metrics": "agent3_entity_metrics.parquet",
    "communities": "agent3_communities.parquet",
    "agent2_features": "agent3_agent2_features.parquet",
    "network_summary": "agent3_network_summary.json",
    "report": "agent3_graph_report.json",
}


@dataclass(frozen=True, slots=True)
class Agent3DemoData:
    output_dir: Path
    report: dict[str, Any]
    network_summary: dict[str, Any]
    nodes: pd.DataFrame
    edges: pd.DataFrame
    entity_metrics: pd.DataFrame
    communities: pd.DataFrame
    agent2_features: pd.DataFrame


def missing_demo_artifacts(output_dir: Path) -> list[Path]:
    return [
        output_dir / artifact
        for artifact in AGENT3_DEMO_ARTIFACTS.values()
        if not (output_dir / artifact).exists()
    ]


def load_agent3_demo_data(output_dir: Path = Path("data/processed")) -> Agent3DemoData:
    missing = missing_demo_artifacts(output_dir)
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Faltan artefactos Agent3 para la demo: {missing_text}")

    return Agent3DemoData(
        output_dir=output_dir,
        report=_read_json(output_dir / AGENT3_DEMO_ARTIFACTS["report"]),
        network_summary=_read_json(output_dir / AGENT3_DEMO_ARTIFACTS["network_summary"]),
        nodes=pd.read_parquet(output_dir / AGENT3_DEMO_ARTIFACTS["nodes"]),
        edges=pd.read_parquet(output_dir / AGENT3_DEMO_ARTIFACTS["edges"]),
        entity_metrics=pd.read_parquet(output_dir / AGENT3_DEMO_ARTIFACTS["entity_metrics"]),
        communities=pd.read_parquet(output_dir / AGENT3_DEMO_ARTIFACTS["communities"]),
        agent2_features=pd.read_parquet(output_dir / AGENT3_DEMO_ARTIFACTS["agent2_features"]),
    )


def build_demo_kpis(data: Agent3DemoData) -> dict[str, int]:
    return {
        "contracts": int(data.report.get("input_rows", len(data.agent2_features))),
        "nodes": int(data.report.get("nodes_rows", len(data.nodes))),
        "edges": int(data.report.get("edges_rows", len(data.edges))),
        "communities": int(data.report.get("community_count", len(data.communities))),
        "largest_component_size": int(data.report.get("largest_component_size", 0)),
        "agent2_features": int(data.report.get("agent2_features_rows", len(data.agent2_features))),
    }


def top_entities(
    data: Agent3DemoData,
    *,
    node_type: str,
    metric: str = "betweenness_centrality",
    limit: int = 10,
) -> pd.DataFrame:
    if data.entity_metrics.empty or metric not in data.entity_metrics.columns:
        return pd.DataFrame()
    filtered = data.entity_metrics[data.entity_metrics["node_type"] == node_type].copy()
    if filtered.empty:
        return filtered
    return filtered.sort_values(
        by=[metric, "neighbor_count", "label"],
        ascending=[False, False, True],
    ).head(limit)


def top_communities(data: Agent3DemoData, *, limit: int = 10) -> pd.DataFrame:
    if data.communities.empty:
        return data.communities
    return data.communities.sort_values(
        by=["contract_count", "node_count", "internal_edge_count"],
        ascending=[False, False, False],
    ).head(limit)


def select_explainable_cases(data: Agent3DemoData) -> list[dict[str, Any]]:
    features = data.agent2_features
    if features.empty:
        return []

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    _append_case(
        selected,
        selected_keys,
        title="Proveedor recurrente",
        signal_type="RF-03",
        row=_first_available(
            features,
            sort_columns=[
                "buyer_supplier_recurrence",
                "buyer_supplier_contract_share",
                "contract_betweenness_centrality",
            ],
            selected_keys=selected_keys,
        ),
    )
    _append_case(
        selected,
        selected_keys,
        title="Concentracion comprador-proveedor",
        signal_type="RF-04",
        row=_first_available(
            features,
            sort_columns=[
                "buyer_supplier_contract_share",
                "buyer_supplier_recurrence",
                "supplier_contracts_count",
            ],
            selected_keys=selected_keys,
        ),
    )
    _append_case(
        selected,
        selected_keys,
        title="Contrato central en la red",
        signal_type="AUX-NETWORK",
        row=_first_available(
            features,
            sort_columns=[
                "contract_betweenness_centrality",
                "community_size",
                "contract_neighbor_count",
            ],
            selected_keys=selected_keys,
        ),
    )
    return selected


def build_demo_subgraph(
    data: Agent3DemoData,
    *,
    max_nodes: int = 80,
    node_types: set[str] | None = None,
    community_id: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = data.entity_metrics.copy()
    if node_types:
        metrics = metrics[metrics["node_type"].isin(node_types)]
    if community_id is not None:
        metrics = metrics[metrics["community_id"] == community_id]
    if metrics.empty:
        return metrics, data.edges.iloc[0:0].copy()

    selected_metrics = metrics.sort_values(
        by=["betweenness_centrality", "neighbor_count", "node_id"],
        ascending=[False, False, True],
    ).head(max_nodes)
    selected_nodes = set(selected_metrics["node_id"].astype(str))
    selected_edges = data.edges[
        data.edges["source_node_id"].isin(selected_nodes)
        & data.edges["target_node_id"].isin(selected_nodes)
    ].copy()
    return selected_metrics, selected_edges


def node_type_counts(data: Agent3DemoData) -> pd.DataFrame:
    return _count_frame(data.nodes, "node_type", "nodes")


def edge_type_counts(data: Agent3DemoData) -> pd.DataFrame:
    return _count_frame(data.edges, "edge_type", "edges")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _count_frame(dataframe: pd.DataFrame, column: str, total_name: str) -> pd.DataFrame:
    if dataframe.empty or column not in dataframe.columns:
        return pd.DataFrame(columns=[column, total_name])
    return (
        dataframe[column]
        .value_counts()
        .rename_axis(column)
        .reset_index(name=total_name)
        .sort_values(total_name, ascending=False)
    )


def _first_available(
    features: pd.DataFrame,
    *,
    sort_columns: list[str],
    selected_keys: set[str],
) -> dict[str, Any] | None:
    available_columns = [column for column in sort_columns if column in features.columns]
    if not available_columns:
        return None
    sorted_features = features.sort_values(
        by=[*available_columns, "contract_key_canon"],
        ascending=[*[False for _ in available_columns], True],
    )
    for record in sorted_features.to_dict("records"):
        contract_key = str(record.get("contract_key_canon", ""))
        if contract_key and contract_key not in selected_keys:
            return record
    return None


def _append_case(
    selected: list[dict[str, Any]],
    selected_keys: set[str],
    *,
    title: str,
    signal_type: str,
    row: dict[str, Any] | None,
) -> None:
    if row is None:
        return
    contract_key = str(row["contract_key_canon"])
    selected_keys.add(contract_key)
    selected.append(
        {
            "title": title,
            "signal_type": signal_type,
            "contract_key_canon": contract_key,
            "evidence": {
                "buyer_supplier_recurrence": row.get("buyer_supplier_recurrence"),
                "buyer_supplier_contract_share": row.get("buyer_supplier_contract_share"),
                "supplier_contracts_count": row.get("supplier_contracts_count"),
                "contract_betweenness_centrality": row.get("contract_betweenness_centrality"),
                "community_id": row.get("community_id"),
                "community_size": row.get("community_size"),
                "has_supplier": row.get("has_supplier"),
            },
            "interpretation": (
                "Senal relacional para priorizar revision humana; no declara fraude "
                "ni sustituye scoring final de Agent2."
            ),
        }
    )
