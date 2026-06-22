from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .graph import build_graph_tables
from .loader import load_canonical_contracts
from .metrics import compute_contract_graph_metrics
from .network_metrics import compute_network_metrics

AGENT3_VERSION = "0.1.0"


def run_agent3(
    *,
    input_path: Path = Path("data/processed/agent2_contracts_canonical.parquet"),
    output_dir: Path = Path("data/processed"),
) -> dict[str, Any]:
    import pandas as pd

    if not input_path.exists():
        raise FileNotFoundError(f"No existe canonico Agent2 para Agent3: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    contracts = load_canonical_contracts(input_path)
    graph_tables = build_graph_tables(contracts)
    metrics = compute_contract_graph_metrics(contracts)
    network_metrics = compute_network_metrics(graph_tables)

    nodes_df = pd.DataFrame(graph_tables.node_records())
    edges_df = pd.DataFrame(graph_tables.edge_records())
    metrics_df = pd.DataFrame([item.as_record() for item in metrics])
    entity_metrics_df = pd.DataFrame(network_metrics.entity_records)
    communities_df = pd.DataFrame(network_metrics.community_records)

    outputs = {
        "nodes": output_dir / "agent3_nodes.parquet",
        "edges": output_dir / "agent3_edges.parquet",
        "contract_metrics": output_dir / "agent3_contract_metrics.parquet",
        "entity_metrics": output_dir / "agent3_entity_metrics.parquet",
        "communities": output_dir / "agent3_communities.parquet",
        "network_summary": output_dir / "agent3_network_summary.json",
        "report": output_dir / "agent3_graph_report.json",
    }
    nodes_df.to_parquet(outputs["nodes"], index=False)
    edges_df.to_parquet(outputs["edges"], index=False)
    metrics_df.to_parquet(outputs["contract_metrics"], index=False)
    entity_metrics_df.to_parquet(outputs["entity_metrics"], index=False)
    communities_df.to_parquet(outputs["communities"], index=False)
    outputs["network_summary"].write_text(
        json.dumps(network_metrics.summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report = {
        "agent": "agent3",
        "agent3_version": AGENT3_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "input_rows": int(len(contracts)),
        "nodes_rows": int(len(nodes_df)),
        "edges_rows": int(len(edges_df)),
        "contract_metrics_rows": int(len(metrics_df)),
        "entity_metrics_rows": int(len(entity_metrics_df)),
        "communities_rows": int(len(communities_df)),
        "component_count": network_metrics.summary["component_count"],
        "community_count": network_metrics.summary["community_count"],
        "largest_component_size": network_metrics.summary["largest_component_size"],
        "largest_community_size": network_metrics.summary["largest_community_size"],
        "nodes_by_type": dict(_count_column(nodes_df, "node_type")),
        "edges_by_type": dict(_count_column(edges_df, "edge_type")),
        "contracts_without_supplier": _warning_count(
            graph_tables.warnings,
            "Contracts without supplier relation:",
        ),
        "contracts_without_cpv": _warning_count(
            graph_tables.warnings,
            "Contracts without CPV relation:",
        ),
        "warnings": graph_tables.warnings,
        "outputs": {name: str(path) for name, path in outputs.items()},
    }
    outputs["report"].write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def _count_column(dataframe: Any, column: str) -> Counter[str]:
    if dataframe.empty or column not in dataframe.columns:
        return Counter()
    return Counter(str(value) for value in dataframe[column].dropna().tolist())


def _warning_count(warnings: list[str], prefix: str) -> int:
    for warning in warnings:
        if warning.startswith(prefix):
            try:
                return int(warning.removeprefix(prefix).strip())
            except ValueError:
                return 0
    return 0
