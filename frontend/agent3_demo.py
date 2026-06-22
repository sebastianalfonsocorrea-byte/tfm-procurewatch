from __future__ import annotations

import os
import sys
from pathlib import Path

import networkx as nx
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCR_DIR = PROJECT_ROOT / "scr"
if str(SCR_DIR) not in sys.path:
    sys.path.insert(0, str(SCR_DIR))

from procurewatch.agent3.demo import (  # noqa: E402
    build_demo_kpis,
    build_demo_subgraph,
    edge_type_counts,
    load_agent3_demo_data,
    missing_demo_artifacts,
    node_type_counts,
    select_explainable_cases,
    top_communities,
    top_entities,
)


def main() -> None:
    st.set_page_config(page_title="Agent3 Graph Demo", layout="wide")
    st.title("Agent3 Graph Demo")

    default_output_dir = os.getenv("PROCUREWATCH_AGENT3_DEMO_DIR", "data/processed")
    output_dir_text = st.sidebar.text_input("Output dir", value=default_output_dir)
    output_dir = Path(output_dir_text)
    missing = missing_demo_artifacts(output_dir)
    if missing:
        st.error("Faltan artefactos Agent3.")
        st.code(
            "python -c \"from procurewatch.cli import main; "
            "raise SystemExit(main(['run-agent3']))\"",
            language="powershell",
        )
        st.dataframe(
            [{"artifact": str(path)} for path in missing],
            use_container_width=True,
            hide_index=True,
        )
        return

    data = load_agent3_demo_data(output_dir)
    kpis = build_demo_kpis(data)

    st.caption(
        "Senales relacionales para revision humana. No declaran fraude ni sustituyen Agent2."
    )
    _render_kpis(kpis)

    summary_tab, network_tab, cases_tab, artifacts_tab = st.tabs(
        ["Resumen", "Red", "Casos", "Artefactos"]
    )
    with summary_tab:
        _render_summary(data)
    with network_tab:
        _render_network(data)
    with cases_tab:
        _render_cases(data)
    with artifacts_tab:
        _render_artifacts(data)


def _render_kpis(kpis: dict[str, int]) -> None:
    columns = st.columns(6)
    labels = [
        ("Contratos", "contracts"),
        ("Nodos", "nodes"),
        ("Aristas", "edges"),
        ("Comunidades", "communities"),
        ("Componente mayor", "largest_component_size"),
        ("Features Agent2", "agent2_features"),
    ]
    for column, (label, key) in zip(columns, labels, strict=False):
        column.metric(label, f"{kpis.get(key, 0):,}".replace(",", "."))


def _render_summary(data) -> None:
    left, right = st.columns(2)
    with left:
        st.subheader("Nodos por tipo")
        node_counts = node_type_counts(data)
        st.plotly_chart(
            px.bar(node_counts, x="node_type", y="nodes", color="node_type"),
            use_container_width=True,
        )
    with right:
        st.subheader("Aristas por tipo")
        edge_counts = edge_type_counts(data)
        st.plotly_chart(
            px.bar(edge_counts, x="edge_type", y="edges", color="edge_type"),
            use_container_width=True,
        )

    st.subheader("Comunidades principales")
    communities = top_communities(data, limit=12)
    st.plotly_chart(
        px.bar(
            communities,
            x="community_id",
            y="contract_count",
            color="node_count",
            hover_data=["buyer_count", "supplier_count", "cpv_count"],
        ),
        use_container_width=True,
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Compradores centrales")
        st.dataframe(
            top_entities(data, node_type="Buyer", limit=10)[
                ["label", "neighbor_count", "betweenness_centrality", "community_id"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    with right:
        st.subheader("Proveedores centrales")
        st.dataframe(
            top_entities(data, node_type="Supplier", limit=10)[
                ["label", "neighbor_count", "betweenness_centrality", "community_id"]
            ],
            use_container_width=True,
            hide_index=True,
        )


def _render_network(data) -> None:
    st.subheader("Subgrafo filtrable")
    left, right, third = st.columns([2, 2, 1])
    with left:
        node_types = st.multiselect(
            "Tipos de nodo",
            options=sorted(data.entity_metrics["node_type"].dropna().unique().tolist()),
            default=["Buyer", "Supplier", "Contract"],
        )
    with right:
        community_values = sorted(data.entity_metrics["community_id"].dropna().unique().tolist())
        community_label = st.selectbox("Comunidad", options=["Todas", *community_values])
    with third:
        max_nodes = st.slider("Nodos", min_value=20, max_value=150, value=70, step=10)

    community_id = None if community_label == "Todas" else int(community_label)
    nodes, edges = build_demo_subgraph(
        data,
        max_nodes=max_nodes,
        node_types=set(node_types) if node_types else None,
        community_id=community_id,
    )
    if nodes.empty:
        st.warning("No hay nodos para el filtro actual.")
        return
    st.plotly_chart(_network_figure(nodes, edges), use_container_width=True)
    st.dataframe(
        nodes[
            [
                "label",
                "node_type",
                "neighbor_count",
                "betweenness_centrality",
                "community_id",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_cases(data) -> None:
    st.subheader("Casos explicables")
    for item in select_explainable_cases(data):
        with st.container(border=True):
            st.markdown(f"**{item['title']}**")
            st.caption(item["contract_key_canon"])
            st.json(item["evidence"], expanded=False)
            st.write(item["interpretation"])


def _render_artifacts(data) -> None:
    st.subheader("Artefactos")
    outputs = data.report.get("outputs", {})
    st.dataframe(
        [{"name": name, "path": path} for name, path in outputs.items()],
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Resumen de red")
    st.json(data.network_summary)


def _network_figure(nodes, edges) -> go.Figure:
    graph = nx.Graph()
    labels = dict(zip(nodes["node_id"], nodes["label"], strict=False))
    node_types = dict(zip(nodes["node_id"], nodes["node_type"], strict=False))
    for node_id in nodes["node_id"]:
        graph.add_node(node_id)
    for row in edges.to_dict("records"):
        graph.add_edge(row["source_node_id"], row["target_node_id"])
    positions = nx.spring_layout(graph, seed=42) if graph.number_of_edges() else {}

    edge_x = []
    edge_y = []
    for source, target in graph.edges:
        source_x, source_y = positions[source]
        target_x, target_y = positions[target]
        edge_x.extend([source_x, target_x, None])
        edge_y.extend([source_y, target_y, None])

    node_x = []
    node_y = []
    hover = []
    color = []
    color_map = {
        "Buyer": "#2563eb",
        "Supplier": "#059669",
        "Contract": "#7c3aed",
        "CPV": "#d97706",
        "Source": "#475569",
    }
    for node_id in graph.nodes:
        x_pos, y_pos = positions.get(node_id, (0, 0))
        node_x.append(x_pos)
        node_y.append(y_pos)
        node_type = node_types.get(node_id, "")
        hover.append(f"{labels.get(node_id, node_id)}<br>{node_type}<br>{node_id}")
        color.append(color_map.get(node_type, "#111827"))

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"width": 1, "color": "#cbd5e1"},
            hoverinfo="none",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers",
            marker={"size": 10, "color": color, "line": {"width": 0}},
            text=hover,
            hoverinfo="text",
        )
    )
    figure.update_layout(
        height=620,
        margin={"l": 0, "r": 0, "t": 20, "b": 0},
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False},
        plot_bgcolor="white",
    )
    return figure


if __name__ == "__main__":
    main()
