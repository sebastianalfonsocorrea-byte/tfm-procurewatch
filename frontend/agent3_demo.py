from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

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
    st.set_page_config(page_title="ProcureWatch MVP", layout="wide")
    st.title("ProcureWatch MVP")

    default_output_dir = os.getenv("PROCUREWATCH_AGENT3_DEMO_DIR", "data/processed")
    output_dir_text = st.sidebar.text_input("Output dir", value=default_output_dir)
    output_dir = Path(output_dir_text)
    default_case_context_path = Path(
        os.getenv(
            "PROCUREWATCH_AGENT4_CASE_CONTEXT",
            str(_default_case_context_path(output_dir)),
        )
    )
    case_context_text = st.sidebar.text_input(
        "Agent4 case context",
        value=str(default_case_context_path),
    )
    case_context = _load_case_context(Path(case_context_text)) if case_context_text else {}
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

    summary_tab, network_tab, cases_tab, case_tab, artifacts_tab = st.tabs(
        ["Resumen", "Red", "Casos", "Ficha", "Artefactos"]
    )
    with summary_tab:
        _render_summary(data)
    with network_tab:
        _render_network(data)
    with cases_tab:
        _render_cases(data)
    with case_tab:
        _render_case_context(case_context)
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


def _render_case_context(payload: dict[str, Any]) -> None:
    st.subheader("Ficha explicable")
    if not payload:
        st.warning("No hay ficha Agent4 cargada.")
        return

    case_context = _dict_value(payload.get("case_context"))
    agent2_score = _dict_value(payload.get("agent2_score")) or _dict_value(
        case_context.get("agent2_score")
    )
    agent3_metrics = _dict_value(case_context.get("agent3_metrics_used"))
    warnings = _list_value(payload.get("warnings")) or _list_value(case_context.get("warnings"))
    citations = _list_value(payload.get("citations")) or _list_value(case_context.get("citations"))
    evidences = _list_value(case_context.get("evidences")) or _list_value(
        payload.get("retrieved_context")
    )

    contract_key = payload.get("contract_key_canon") or case_context.get("contract_key_canon")
    answer = payload.get("answer") or case_context.get("summary") or "Sin resumen disponible."

    columns = st.columns(4)
    columns[0].metric("Risk score", _format_metric(agent2_score.get("risk_score")))
    columns[1].metric("Red flags", len(_list_value(agent2_score.get("red_flags"))))
    columns[2].metric("Evidencias", len(evidences))
    columns[3].metric("Citas", len(citations))

    st.caption(str(contract_key or "Contrato no informado"))
    st.write(str(answer))

    if warnings:
        st.warning("\n".join(f"- {item}" for item in warnings))

    left, right = st.columns(2)
    with left:
        st.subheader("Agent2")
        st.json(agent2_score)
    with right:
        st.subheader("Agent3")
        if agent3_metrics:
            st.json(agent3_metrics)
        else:
            st.info("Sin metricas Agent3 para este caso.")

    st.subheader("Evidencias")
    if evidences:
        st.dataframe(evidences, use_container_width=True, hide_index=True)
    else:
        st.info("Sin evidencias documentales recuperadas.")

    st.subheader("Citas")
    if citations:
        st.dataframe(citations, use_container_width=True, hide_index=True)
    else:
        st.info("Sin citas documentales.")


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


def _default_case_context_path(output_dir: Path) -> Path:
    candidates = [
        output_dir / "agent4_case_context_integrated_demo.json",
        output_dir / "agent4_case_context.json",
        Path("data/processed/agent4_case_context.json"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_case_context(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        st.warning(f"No se pudo leer la ficha Agent4: {path}")
        return {}


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _format_metric(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


if __name__ == "__main__":
    main()
