from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .schemas import GraphTables

BETWEENNESS_EXACT_NODE_LIMIT = 1000
BETWEENNESS_SAMPLE_SIZE = 500
NETWORK_RANDOM_SEED = 42


@dataclass(frozen=True, slots=True)
class NetworkMetricsResult:
    entity_records: list[dict[str, Any]]
    community_records: list[dict[str, Any]]
    summary: dict[str, Any]


def compute_network_metrics(graph_tables: GraphTables) -> NetworkMetricsResult:
    graph = _build_simple_graph(graph_tables)
    if graph.number_of_nodes() == 0:
        return NetworkMetricsResult(
            entity_records=[],
            community_records=[],
            summary={
                "nodes": 0,
                "edges": 0,
                "component_count": 0,
                "community_count": 0,
                "modularity": None,
                "largest_component_size": 0,
                "largest_community_size": 0,
                "betweenness_mode": "empty",
                "betweenness_sample_size": 0,
            },
        )

    component_by_node, component_sizes = _connected_components(graph)
    community_by_node, community_sizes, modularity = _louvain_communities(graph)
    degree_centrality = _rounded_mapping(_degree_centrality(graph))
    betweenness, betweenness_mode, betweenness_sample_size = _betweenness_centrality(graph)

    entity_records = []
    for node_id in sorted(graph.nodes):
        node_data = graph.nodes[node_id]
        component_id = component_by_node[node_id]
        community_id = community_by_node[node_id]
        entity_records.append(
            {
                "node_id": node_id,
                "node_type": node_data.get("node_type", ""),
                "label": node_data.get("label", ""),
                "neighbor_count": int(graph.degree[node_id]),
                "degree_centrality": degree_centrality.get(node_id, 0.0),
                "betweenness_centrality": betweenness.get(node_id, 0.0),
                "component_id": component_id,
                "component_size": component_sizes[component_id],
                "community_id": community_id,
                "community_size": community_sizes[community_id],
            }
        )

    community_records = _community_records(graph, community_by_node, component_by_node)
    summary = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "component_count": len(component_sizes),
        "community_count": len(community_sizes),
        "modularity": modularity,
        "largest_component_size": max(component_sizes.values(), default=0),
        "largest_community_size": max(community_sizes.values(), default=0),
        "largest_component_contract_count": _largest_group_contract_count(
            graph,
            component_by_node,
        ),
        "largest_community_contract_count": _largest_group_contract_count(
            graph,
            community_by_node,
        ),
        "betweenness_mode": betweenness_mode,
        "betweenness_sample_size": betweenness_sample_size,
        "node_types": dict(
            Counter(data.get("node_type", "") for _, data in graph.nodes(data=True))
        ),
    }
    return NetworkMetricsResult(
        entity_records=entity_records,
        community_records=community_records,
        summary=summary,
    )


def _build_simple_graph(graph_tables: GraphTables):
    try:
        import networkx as nx
    except ImportError as exc:
        raise RuntimeError("networkx is required to compute Agent3 network metrics") from exc

    graph = nx.Graph()
    for node in graph_tables.nodes:
        graph.add_node(
            node.node_id,
            node_type=node.node_type,
            label=node.label,
            **node.attributes,
        )
    for edge in graph_tables.edges:
        if graph.has_edge(edge.source_node_id, edge.target_node_id):
            graph.edges[edge.source_node_id, edge.target_node_id]["edge_count"] += 1
        else:
            graph.add_edge(
                edge.source_node_id,
                edge.target_node_id,
                edge_count=1,
            )
    return graph


def _connected_components(graph: Any) -> tuple[dict[str, int], dict[int, int]]:
    import networkx as nx

    sorted_components = sorted(
        (sorted(component) for component in nx.connected_components(graph)),
        key=lambda component: (-len(component), component[0]),
    )
    component_by_node = {}
    component_sizes = {}
    for component_id, nodes in enumerate(sorted_components):
        component_sizes[component_id] = len(nodes)
        for node_id in nodes:
            component_by_node[node_id] = component_id
    return component_by_node, component_sizes


def _louvain_communities(
    graph: Any,
) -> tuple[dict[str, int], dict[int, int], float | None]:
    if graph.number_of_edges() == 0:
        raw_partition = {node_id: index for index, node_id in enumerate(sorted(graph.nodes))}
        modularity = None
    else:
        try:
            import community.community_louvain as community_louvain
        except ImportError as exc:
            raise RuntimeError(
                "python-louvain is required to compute Agent3 Louvain communities"
            ) from exc
        raw_partition = community_louvain.best_partition(
            graph,
            random_state=NETWORK_RANDOM_SEED,
        )
        modularity = round(float(community_louvain.modularity(raw_partition, graph)), 10)

    group_by_node, group_sizes = _stable_group_ids(raw_partition)
    return group_by_node, group_sizes, modularity


def _stable_group_ids(raw_partition: dict[str, int]) -> tuple[dict[str, int], dict[int, int]]:
    grouped_nodes: dict[int, list[str]] = defaultdict(list)
    for node_id, raw_group in raw_partition.items():
        grouped_nodes[raw_group].append(node_id)

    sorted_groups = sorted(
        (sorted(nodes) for nodes in grouped_nodes.values()),
        key=lambda nodes: (-len(nodes), nodes[0]),
    )
    group_by_node = {}
    group_sizes = {}
    for group_id, nodes in enumerate(sorted_groups):
        group_sizes[group_id] = len(nodes)
        for node_id in nodes:
            group_by_node[node_id] = group_id
    return group_by_node, group_sizes


def _degree_centrality(graph: Any) -> dict[str, float]:
    import networkx as nx

    return nx.degree_centrality(graph)


def _betweenness_centrality(graph: Any) -> tuple[dict[str, float], str, int]:
    import networkx as nx

    node_count = graph.number_of_nodes()
    if node_count <= BETWEENNESS_EXACT_NODE_LIMIT:
        return (
            _rounded_mapping(nx.betweenness_centrality(graph, normalized=True)),
            "exact",
            node_count,
        )

    sample_size = min(BETWEENNESS_SAMPLE_SIZE, node_count)
    return (
        _rounded_mapping(
            nx.betweenness_centrality(
                graph,
                k=sample_size,
                normalized=True,
                seed=NETWORK_RANDOM_SEED,
            )
        ),
        "sampled",
        sample_size,
    )


def _community_records(
    graph: Any,
    community_by_node: dict[str, int],
    component_by_node: dict[str, int],
) -> list[dict[str, Any]]:
    nodes_by_community: dict[int, list[str]] = defaultdict(list)
    internal_edges_by_community: Counter[int] = Counter()
    for node_id, community_id in community_by_node.items():
        nodes_by_community[community_id].append(node_id)

    for source, target in graph.edges:
        source_community = community_by_node[source]
        if source_community == community_by_node[target]:
            internal_edges_by_community[source_community] += 1

    records = []
    for community_id in sorted(nodes_by_community):
        nodes = sorted(nodes_by_community[community_id])
        node_types = Counter(str(graph.nodes[node_id].get("node_type", "")) for node_id in nodes)
        component_ids = {component_by_node[node_id] for node_id in nodes}
        records.append(
            {
                "community_id": community_id,
                "component_id": min(component_ids),
                "component_count": len(component_ids),
                "node_count": len(nodes),
                "contract_count": node_types.get("Contract", 0),
                "buyer_count": node_types.get("Buyer", 0),
                "supplier_count": node_types.get("Supplier", 0),
                "cpv_count": node_types.get("CPV", 0),
                "source_count": node_types.get("Source", 0),
                "internal_edge_count": internal_edges_by_community[community_id],
            }
        )
    return records


def _largest_group_contract_count(graph: Any, group_by_node: dict[str, int]) -> int:
    contracts_by_group: Counter[int] = Counter()
    for node_id, group_id in group_by_node.items():
        if graph.nodes[node_id].get("node_type") == "Contract":
            contracts_by_group[group_id] += 1
    return max(contracts_by_group.values(), default=0)


def _rounded_mapping(values: dict[str, float]) -> dict[str, float]:
    return {key: round(float(value), 10) for key, value in values.items()}
