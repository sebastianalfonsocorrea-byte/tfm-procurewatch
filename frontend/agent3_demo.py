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

NODE_TYPE_LABELS = {
    "Buyer": "Comprador",
    "Supplier": "Proveedor",
    "Contract": "Contrato",
    "CPV": "CPV",
    "Source": "Fuente",
}

EDGE_TYPE_LABELS = {
    "PUBLISHED": "Publica",
    "AWARDED_TO": "Adjudicado a",
    "HAS_CPV": "CPV",
    "FROM_SOURCE": "Fuente",
}

FLAG_LABELS = {
    "risky_procedure": "Procedimiento sensible",
    "awarded_above_estimate": "Adjudicado sobre el estimado",
    "missing_supplier": "Proveedor no informado",
    "single_bidder": "Baja concurrencia",
}

FLAG_EXPLANATIONS = {
    "risky_procedure": "El procedimiento requiere revision porque reduce competencia o publicidad.",
    "awarded_above_estimate": "El importe adjudicado supera el valor estimado registrado.",
    "missing_supplier": "Falta una relacion clave para explicar la adjudicacion.",
    "single_bidder": "La concurrencia limitada puede elevar prioridad de revision.",
}


def main() -> None:
    st.set_page_config(page_title="ProcureWatch MVP", layout="wide")
    _apply_page_style()

    st.title("ProcureWatch MVP")
    st.caption(
        "Demo multiagente para revisar contratacion publica con grafo, scoring y evidencia "
        "documental. No declara fraude; prioriza revision humana trazable."
    )

    output_dir, case_context_path = _render_sidebar_inputs()
    case_context = _load_case_context(case_context_path) if case_context_path else {}

    missing = missing_demo_artifacts(output_dir)
    if missing:
        _render_missing_artifacts(output_dir, missing)
        return

    data = load_agent3_demo_data(output_dir)
    kpis = build_demo_kpis(data)
    selected_contract = _render_contract_selector(data, case_context)
    case_view = _build_case_view(data, case_context, selected_contract)

    _render_context_overview(
        data=data,
        kpis=kpis,
        output_dir=output_dir,
        case_context_path=case_context_path,
        case_context=case_context,
        case_view=case_view,
    )

    overview_tab, network_tab, case_tab, evidences_tab, debug_tab = st.tabs(
        ["Vista general", "Explorar red", "Caso", "Evidencias", "Debug"]
    )
    with overview_tab:
        _render_overview(data, kpis, case_view)
    with network_tab:
        _render_network(data, selected_contract)
    with case_tab:
        _render_case(case_view)
    with evidences_tab:
        _render_evidences(case_view)
    with debug_tab:
        _render_debug(data, case_context, output_dir, case_context_path, case_view)


def _render_sidebar_inputs() -> tuple[Path, Path | None]:
    st.sidebar.header("Datos cargados")
    default_output_dir = os.getenv("PROCUREWATCH_AGENT3_DEMO_DIR", "data/processed")
    output_dir_text = st.sidebar.text_input(
        "Carpeta de demo cargada",
        value=default_output_dir,
        help="Debe contener los parquet/json generados por Agent3.",
    )
    output_dir = Path(output_dir_text)
    default_case_context_path = Path(
        os.getenv(
            "PROCUREWATCH_AGENT4_CASE_CONTEXT",
            str(_default_case_context_path(output_dir)),
        )
    )
    case_context_text = st.sidebar.text_input(
        "Ficha documental del contrato",
        value=str(default_case_context_path),
        help="JSON generado por Agent4 con resumen, evidencias y citas.",
    )
    st.sidebar.caption(
        "Agent3 alimenta el grafo. Agent4 alimenta la ficha explicable del contrato."
    )
    return output_dir, Path(case_context_text) if case_context_text else None


def _render_contract_selector(data, case_context: dict[str, Any]) -> str:
    st.sidebar.header("Navegacion")
    options = _contract_options(data)
    if not options:
        st.sidebar.warning("No hay contratos disponibles en los artefactos Agent3.")
        return ""

    preferred_contract = _case_context_contract_key(case_context)
    index = options.index(preferred_contract) if preferred_contract in options else 0
    return st.sidebar.selectbox(
        "Contrato a revisar",
        options=options,
        index=index,
        format_func=lambda key: _contract_option_label(data, key),
        help="La red sigue siendo la entrada principal; este selector fija el contrato explicado.",
    )


def _render_context_overview(
    *,
    data,
    kpis: dict[str, int],
    output_dir: Path,
    case_context_path: Path | None,
    case_context: dict[str, Any],
    case_view: dict[str, Any],
) -> None:
    left, middle, right = st.columns([1.4, 1.2, 1])
    with left:
        st.markdown("### Que estas viendo")
        st.write(
            "La demo carga contratos transformados en una red: compradores, proveedores, "
            "contratos, CPV y fuentes. Desde esa red se selecciona un contrato y se explica "
            "con senales de riesgo y evidencia documental."
        )
    with middle:
        st.markdown("### Datos usados")
        st.write(f"**Grafo Agent3:** `{output_dir}`")
        if case_context:
            st.write(f"**Ficha Agent4:** `{case_context_path}`")
        else:
            st.warning("No hay ficha documental Agent4 cargada.")
    with right:
        st.markdown("### Caso activo")
        st.write(f"**{case_view.get('contract_key') or 'Sin contrato'}**")
        st.write(str(case_view.get("title") or "Sin titulo disponible."))

    if case_view.get("case_context_contract") and not case_view.get("case_context_matches"):
        st.warning(
            "La ficha documental cargada pertenece a "
            f"{case_view['case_context_contract']}; el contrato seleccionado es "
            f"{case_view['contract_key']}. Para este contrato solo se muestran senales "
            "del grafo."
        )

    _render_kpis(kpis)
    _render_pipeline_strip(data, case_context)


def _render_kpis(kpis: dict[str, int]) -> None:
    columns = st.columns(6)
    labels = [
        ("Contratos", "contracts"),
        ("Nodos de red", "nodes"),
        ("Relaciones", "edges"),
        ("Comunidades", "communities"),
        ("Mayor componente", "largest_component_size"),
        ("Contratos con senales", "agent2_features"),
    ]
    for column, (label, key) in zip(columns, labels, strict=False):
        column.metric(label, _format_int(kpis.get(key, 0)))


def _render_pipeline_strip(data, case_context: dict[str, Any]) -> None:
    has_agent3 = not data.agent2_features.empty
    has_agent4 = bool(case_context)
    items = [
        ("Agent1/2", "Contrato canonico y scoring determinista", True),
        ("Agent3", "Grafo de entidades y relaciones", has_agent3),
        ("Agent4", "Ficha documental con citas", has_agent4),
    ]
    columns = st.columns(len(items))
    for column, (title, description, active) in zip(columns, items, strict=False):
        state = "Activo" if active else "Pendiente"
        column.markdown(
            f"""
            <div class="pw-step {"pw-step-on" if active else "pw-step-off"}">
                <div class="pw-step-title">{title}</div>
                <div class="pw-step-state">{state}</div>
                <div class="pw-step-text">{description}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_overview(data, kpis: dict[str, int], case_view: dict[str, Any]) -> None:
    st.subheader("Lectura rapida")
    left, right = st.columns([1.2, 1])
    with left:
        st.write(
            "Empieza por la red: los contratos se conectan con compradores, proveedores, CPV "
            "y fuente. Las comunidades ayudan a ver grupos de relacion. Despues baja al caso "
            "seleccionado para revisar senales y evidencia."
        )
        _render_recommended_cases(data, case_view.get("contract_key"))
    with right:
        st.markdown("#### Caso seleccionado")
        _render_case_snapshot(case_view)

    _render_distribution_charts(data)

    st.subheader("Entidades centrales")
    left, right = st.columns(2)
    with left:
        _render_entity_table(data, node_type="Buyer", title="Compradores con mas peso")
    with right:
        _render_entity_table(data, node_type="Supplier", title="Proveedores con mas peso")


def _render_recommended_cases(data, selected_contract: str | None) -> None:
    st.markdown("#### Casos sugeridos por Agent3")
    rows = []
    for item in select_explainable_cases(data):
        rows.append(
            {
                "contrato": item["contract_key_canon"],
                "senal": item["title"],
                "tipo": item["signal_type"],
                "seleccionado": "si" if item["contract_key_canon"] == selected_contract else "",
            }
        )
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Agent3 no ha seleccionado casos explicables en este lote.")


def _render_case_snapshot(case_view: dict[str, Any]) -> None:
    columns = st.columns(2)
    columns[0].metric("Riesgo Agent2", _format_metric(case_view.get("risk_score")))
    columns[1].metric("Senales de riesgo", str(len(case_view.get("red_flags", []))))
    st.write(f"**Comprador:** {case_view.get('buyer_name') or 'No informado'}")
    st.write(f"**Proveedor:** {case_view.get('supplier_name') or 'No informado'}")
    st.write(f"**Titulo:** {case_view.get('title') or 'No informado'}")


def _render_distribution_charts(data) -> None:
    st.subheader("Como se reparte la red")
    left, right = st.columns(2)
    with left:
        node_counts = node_type_counts(data)
        if not node_counts.empty:
            node_counts = node_counts.copy()
            node_counts["tipo"] = node_counts["node_type"].map(_node_type_label)
            st.plotly_chart(
                px.bar(node_counts, x="tipo", y="nodes", color="tipo"),
                width="stretch",
            )
        else:
            st.info("No hay nodos para representar.")
    with right:
        edge_counts = edge_type_counts(data)
        if not edge_counts.empty:
            edge_counts = edge_counts.copy()
            edge_counts["relacion"] = edge_counts["edge_type"].map(_edge_type_label)
            st.plotly_chart(
                px.bar(edge_counts, x="relacion", y="edges", color="relacion"),
                width="stretch",
            )
        else:
            st.info("No hay relaciones para representar.")

    communities = top_communities(data, limit=12)
    if not communities.empty:
        st.markdown("#### Comunidades principales")
        st.plotly_chart(
            px.bar(
                communities,
                x="community_id",
                y="contract_count",
                color="node_count",
                hover_data=["buyer_count", "supplier_count", "cpv_count"],
                labels={
                    "community_id": "Comunidad",
                    "contract_count": "Contratos",
                    "node_count": "Nodos",
                },
            ),
            width="stretch",
        )


def _render_entity_table(data, *, node_type: str, title: str) -> None:
    st.markdown(f"#### {title}")
    entities = top_entities(data, node_type=node_type, limit=10)
    if entities.empty:
        st.info("No hay entidades disponibles.")
        return
    table = entities[["label", "neighbor_count", "betweenness_centrality", "community_id"]].rename(
        columns={
            "label": "entidad",
            "neighbor_count": "conexiones",
            "betweenness_centrality": "centralidad",
            "community_id": "comunidad",
        }
    )
    st.dataframe(table, width="stretch", hide_index=True)


def _render_network(data, selected_contract: str) -> None:
    st.subheader("Explorar red")
    st.write(
        "El grafo muestra como se conectan contratos, compradores, proveedores, CPV y fuentes. "
        "El contrato seleccionado aparece resaltado."
    )
    left, right, third = st.columns([2, 2, 1])
    with left:
        available_types = sorted(data.entity_metrics["node_type"].dropna().unique().tolist())
        node_types = st.multiselect(
            "Tipos de entidad",
            options=available_types,
            default=[item for item in ["Buyer", "Supplier", "Contract"] if item in available_types],
            format_func=_node_type_label,
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
    nodes, edges = _ensure_focus_contract(data, nodes, edges, selected_contract)
    if nodes.empty:
        st.warning("No hay nodos para el filtro actual.")
        return

    st.plotly_chart(
        _network_figure(nodes, edges, focus_contract=selected_contract),
        width="stretch",
    )
    st.caption("Azul: comprador. Verde: proveedor. Violeta: contrato. Ambar: CPV. Gris: fuente.")
    table = nodes[
        [
            "label",
            "node_type",
            "neighbor_count",
            "betweenness_centrality",
            "community_id",
        ]
    ].copy()
    table["node_type"] = table["node_type"].map(_node_type_label)
    table = table.rename(
        columns={
            "label": "entidad",
            "node_type": "tipo",
            "neighbor_count": "conexiones",
            "betweenness_centrality": "centralidad",
            "community_id": "comunidad",
        }
    )
    st.dataframe(table, width="stretch", hide_index=True)


def _render_case(case_view: dict[str, Any]) -> None:
    st.subheader("Caso seleccionado")
    if not case_view.get("contract_key"):
        st.warning("No hay contrato seleccionado.")
        return

    if case_view.get("case_context_contract") and not case_view.get("case_context_matches"):
        st.warning(
            "La ficha Agent4 cargada no corresponde a este contrato. Cambia el selector o "
            "carga la ficha documental correcta."
        )

    columns = st.columns(4)
    columns[0].metric("Riesgo Agent2", _format_metric(case_view.get("risk_score")))
    columns[1].metric("Nivel", str(case_view.get("risk_level") or "n/a"))
    columns[2].metric("Senales", str(len(case_view.get("red_flags", []))))
    columns[3].metric("Evidencias", str(len(case_view.get("evidences", []))))

    st.markdown("#### Contexto del contrato")
    st.dataframe(
        _contract_context_rows(case_view),
        width="stretch",
        hide_index=True,
    )

    left, right = st.columns(2)
    with left:
        st.markdown("#### Senales de riesgo Agent2")
        rows = _agent2_signal_rows(case_view)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("No hay scoring Agent2 cargado para este contrato.")
    with right:
        st.markdown("#### Senales relacionales Agent3")
        rows = _agent3_signal_rows(case_view)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("No hay metricas Agent3 disponibles para este contrato.")

    summary = case_view.get("summary")
    if summary:
        st.markdown("#### Resumen Agent4")
        st.write(str(summary))

    warnings = case_view.get("warnings", [])
    if warnings:
        st.warning("\n".join(f"- {item}" for item in warnings))


def _render_evidences(case_view: dict[str, Any]) -> None:
    st.subheader("Evidencias documentales")
    if case_view.get("case_context_contract") and not case_view.get("case_context_matches"):
        st.warning(
            "La ficha documental cargada pertenece a otro contrato, por eso no se muestran "
            "evidencias aqui."
        )
        return

    evidences = case_view.get("evidences", [])
    citations = case_view.get("citations", [])
    if not evidences:
        st.info(
            "No hay evidencias documentales recuperadas para este contrato. Agent4 debe "
            "indicarlo explicitamente y no inventar conclusiones."
        )
        return

    for index, evidence in enumerate(evidences, start=1):
        with st.container(border=True):
            st.markdown(f"#### Evidencia {index}")
            left, right = st.columns([1, 2])
            with left:
                st.write(f"**Documento:** {evidence.get('document_id', 'n/a')}")
                st.write(f"**Tipo:** {evidence.get('document_type', 'n/a')}")
                st.write(f"**Fuente:** {evidence.get('source', 'n/a')}")
                st.write(f"**Score retrieval:** {_format_metric(evidence.get('score'))}")
            with right:
                st.write(str(evidence.get("text_excerpt") or "Sin extracto disponible."))

    st.markdown("#### Citas trazables")
    if citations:
        st.dataframe(
            [{"cita": citation} for citation in citations],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No hay citas documentales asociadas.")


def _render_debug(
    data,
    case_context: dict[str, Any],
    output_dir: Path,
    case_context_path: Path | None,
    case_view: dict[str, Any],
) -> None:
    st.subheader("Debug / artefactos tecnicos")
    st.write(
        "Esta zona conserva trazabilidad para desarrollo y memoria tecnica. La demo principal "
        "no depende de leer estos JSON manualmente."
    )
    outputs = data.report.get("outputs", {})
    st.dataframe(
        [{"artefacto": name, "ruta": path} for name, path in outputs.items()],
        width="stretch",
        hide_index=True,
    )

    with st.expander("Rutas cargadas", expanded=False):
        st.write(f"Carpeta Agent3: `{output_dir}`")
        st.write(f"Ficha Agent4: `{case_context_path}`")
    with st.expander("Resumen de red Agent3", expanded=False):
        st.json(data.network_summary)
    with st.expander("Fila Agent3 del contrato seleccionado", expanded=False):
        st.json(case_view.get("agent3_metrics", {}))
    with st.expander("Payload Agent4 completo", expanded=False):
        if case_context:
            st.json(case_context)
        else:
            st.info("No hay payload Agent4 cargado.")


def _network_figure(nodes, edges, *, focus_contract: str | None = None) -> go.Figure:
    graph = nx.Graph()
    labels = dict(zip(nodes["node_id"], nodes["label"], strict=False))
    node_types = dict(zip(nodes["node_id"], nodes["node_type"], strict=False))
    focus_node_id = f"contract:{focus_contract}" if focus_contract else None

    for node_id in nodes["node_id"]:
        graph.add_node(node_id)
    for row in edges.to_dict("records"):
        graph.add_edge(row["source_node_id"], row["target_node_id"])
    positions = nx.spring_layout(graph, seed=42) if graph.number_of_nodes() else {}

    edge_x = []
    edge_y = []
    for source, target in graph.edges:
        source_x, source_y = positions[source]
        target_x, target_y = positions[target]
        edge_x.extend([source_x, target_x, None])
        edge_y.extend([source_y, target_y, None])

    color_map = {
        "Buyer": "#2563eb",
        "Supplier": "#059669",
        "Contract": "#7c3aed",
        "CPV": "#d97706",
        "Source": "#475569",
    }
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"width": 1, "color": "#cbd5e1"},
            hoverinfo="none",
            showlegend=False,
        )
    )

    for node_type in sorted(set(node_types.values())):
        node_ids = [node_id for node_id in graph.nodes if node_types.get(node_id) == node_type]
        node_x = []
        node_y = []
        hover = []
        sizes = []
        line_widths = []
        for node_id in node_ids:
            x_pos, y_pos = positions.get(node_id, (0, 0))
            node_x.append(x_pos)
            node_y.append(y_pos)
            hover.append(f"{labels.get(node_id, node_id)}<br>{_node_type_label(node_type)}")
            sizes.append(18 if node_id == focus_node_id else 10)
            line_widths.append(3 if node_id == focus_node_id else 0)
        figure.add_trace(
            go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers",
                marker={
                    "size": sizes,
                    "color": color_map.get(node_type, "#111827"),
                    "line": {"width": line_widths, "color": "#111827"},
                },
                text=hover,
                hoverinfo="text",
                name=_node_type_label(node_type),
            )
        )

    figure.update_layout(
        height=620,
        margin={"l": 0, "r": 0, "t": 20, "b": 0},
        legend={"orientation": "h", "y": 1.02, "x": 0},
        xaxis={"visible": False},
        yaxis={"visible": False},
        plot_bgcolor="white",
    )
    return figure


def _build_case_view(data, payload: dict[str, Any], selected_contract: str) -> dict[str, Any]:
    case_context = _dict_value(payload.get("case_context"))
    case_context_contract = _case_context_contract_key(payload)
    context_matches = bool(case_context_contract and case_context_contract == selected_contract)
    matched_context = case_context if context_matches else {}
    agent2_score = _dict_value(payload.get("agent2_score")) if context_matches else {}
    if not agent2_score and context_matches:
        agent2_score = _dict_value(matched_context.get("agent2_score"))

    feature_row = _row_for_contract(data.agent2_features, selected_contract)
    contract_row = _contract_node_record(data, selected_contract)
    contract_fields = _dict_value(matched_context.get("contract_fields_used"))
    agent3_metrics = _dict_value(matched_context.get("agent3_metrics_used")) or feature_row
    evidences = _list_value(matched_context.get("evidences"))
    if not evidences and context_matches:
        evidences = _list_value(payload.get("retrieved_context"))
    citations = _list_value(payload.get("citations")) or _list_value(
        matched_context.get("citations")
    )
    warnings = _list_value(payload.get("warnings")) or _list_value(matched_context.get("warnings"))
    red_flags = _list_value(agent2_score.get("red_flags"))

    return {
        "contract_key": selected_contract,
        "case_context_contract": case_context_contract,
        "case_context_matches": context_matches,
        "title": _first_text(
            contract_fields.get("contract_title"),
            contract_row.get("contract_title"),
            selected_contract,
        ),
        "buyer_name": _first_text(
            contract_fields.get("buyer_name"),
            _connected_node_label(data, selected_contract, edge_type="PUBLISHED"),
        ),
        "supplier_name": _first_text(
            contract_fields.get("supplier_name"),
            _connected_node_label(data, selected_contract, edge_type="AWARDED_TO"),
        ),
        "procedure": _first_text(contract_fields.get("procedure"), "No informado"),
        "estimated_value": contract_fields.get("estimated_value_eur"),
        "awarded_value": contract_fields.get("awarded_value_eur"),
        "publication_date": contract_fields.get("publication_date"),
        "award_date": contract_fields.get("award_date"),
        "source": _first_text(contract_fields.get("source"), feature_row.get("source")),
        "source_record_id": _first_text(
            contract_fields.get("source_record_id"),
            feature_row.get("source_record_id"),
        ),
        "cpv_codes": _first_text(
            contract_fields.get("cpv_code_list"),
            contract_fields.get("cpv_codes_raw"),
            ", ".join(_connected_node_labels(data, selected_contract, edge_type="HAS_CPV")),
        ),
        "risk_score": agent2_score.get("risk_score"),
        "risk_level": agent2_score.get("risk_level"),
        "red_flags": red_flags,
        "agent2_score": agent2_score,
        "agent3_metrics": agent3_metrics,
        "evidences": evidences,
        "citations": citations,
        "warnings": warnings,
        "summary": payload.get("answer") if context_matches else matched_context.get("summary"),
    }


def _contract_context_rows(case_view: dict[str, Any]) -> list[dict[str, str]]:
    rows = [
        ("Contrato", case_view.get("contract_key")),
        ("Titulo", case_view.get("title")),
        ("Comprador", case_view.get("buyer_name")),
        ("Proveedor", case_view.get("supplier_name")),
        ("Procedimiento", case_view.get("procedure")),
        ("Valor estimado", _format_money(case_view.get("estimated_value"))),
        ("Valor adjudicado", _format_money(case_view.get("awarded_value"))),
        ("CPV", case_view.get("cpv_codes")),
        ("Fecha publicacion", case_view.get("publication_date")),
        ("Fecha adjudicacion", case_view.get("award_date")),
        ("Fuente", case_view.get("source")),
        ("Registro fuente", case_view.get("source_record_id")),
    ]
    return [{"campo": label, "valor": str(value)} for label, value in rows if not _is_blank(value)]


def _agent2_signal_rows(case_view: dict[str, Any]) -> list[dict[str, str]]:
    agent2_score = _dict_value(case_view.get("agent2_score"))
    evidence = _dict_value(agent2_score.get("evidence"))
    rows = []
    for flag in case_view.get("red_flags", []):
        rows.append(
            {
                "senal": FLAG_LABELS.get(str(flag), str(flag)),
                "dato usado": _agent2_flag_value(str(flag), evidence),
                "lectura": FLAG_EXPLANATIONS.get(str(flag), "Senal para priorizar revision."),
            }
        )
    return rows


def _agent3_signal_rows(case_view: dict[str, Any]) -> list[dict[str, str]]:
    metrics = _dict_value(case_view.get("agent3_metrics"))
    metric_specs = [
        (
            "buyer_supplier_recurrence",
            "Recurrencia comprador-proveedor",
            "Contratos relacionados entre el mismo comprador y proveedor.",
        ),
        (
            "buyer_supplier_contract_share",
            "Peso de la relacion comprador-proveedor",
            "Parte de contratos del comprador conectados con ese proveedor.",
        ),
        (
            "supplier_contracts_count",
            "Contratos del proveedor en la red",
            "Cuantos contratos conecta este proveedor dentro del lote.",
        ),
        (
            "contract_betweenness_centrality",
            "Centralidad del contrato",
            "Indica si el contrato actua como puente dentro de la red.",
        ),
        (
            "community_size",
            "Tamano de comunidad",
            "Numero de entidades agrupadas alrededor del caso.",
        ),
        ("cpv_count", "CPV asociados", "Numero de codigos CPV vinculados al contrato."),
    ]
    rows = []
    for key, label, reading in metric_specs:
        value = metrics.get(key)
        if _is_blank(value):
            continue
        if key == "buyer_supplier_contract_share":
            formatted = _format_percent(value)
        else:
            formatted = _format_metric(value)
        rows.append({"senal": label, "valor": formatted, "lectura": reading})
    return rows


def _agent2_flag_value(flag: str, evidence: dict[str, Any]) -> str:
    if flag == "risky_procedure":
        return str(evidence.get("procedure") or "Procedimiento no informado")
    if flag == "awarded_above_estimate":
        estimated = _format_money(evidence.get("estimated_value_eur"))
        awarded = _format_money(evidence.get("awarded_value_eur"))
        return f"Estimado {estimated}; adjudicado {awarded}"
    return "Ver evidencia Agent2"


def _ensure_focus_contract(data, nodes, edges, selected_contract: str):
    if not selected_contract:
        return nodes, edges
    focus_id = f"contract:{selected_contract}"
    if focus_id in set(nodes["node_id"].astype(str)):
        return nodes, edges

    focus_node = data.entity_metrics[data.entity_metrics["node_id"].astype(str) == focus_id]
    if focus_node.empty:
        return nodes, edges
    selected_nodes = set(nodes["node_id"].astype(str))
    focus_edges = data.edges[
        (data.edges["source_node_id"].astype(str).isin({focus_id} | selected_nodes))
        & (data.edges["target_node_id"].astype(str).isin({focus_id} | selected_nodes))
    ]
    return _concat_frames(nodes, focus_node), _concat_frames(edges, focus_edges)


def _contract_options(data) -> list[str]:
    if data.agent2_features.empty or "contract_key_canon" not in data.agent2_features.columns:
        return []
    values = [
        str(value)
        for value in data.agent2_features["contract_key_canon"].dropna().unique().tolist()
        if str(value)
    ]
    return sorted(values)


def _contract_option_label(data, contract_key: str) -> str:
    record = _contract_node_record(data, contract_key)
    title = record.get("contract_title")
    if title and str(title) != contract_key:
        return f"{contract_key} - {title}"
    return contract_key


def _contract_node_record(data, contract_key: str) -> dict[str, Any]:
    if data.nodes.empty or "contract_key_canon" not in data.nodes.columns:
        return {}
    matches = data.nodes[
        (data.nodes["node_type"].astype(str) == "Contract")
        & (data.nodes["contract_key_canon"].astype(str) == str(contract_key))
    ]
    if matches.empty:
        return {}
    return _clean_record(matches.iloc[0].to_dict())


def _connected_node_label(data, contract_key: str, *, edge_type: str) -> str:
    labels = _connected_node_labels(data, contract_key, edge_type=edge_type)
    return labels[0] if labels else ""


def _connected_node_labels(data, contract_key: str, *, edge_type: str) -> list[str]:
    if data.edges.empty:
        return []
    contract_node_id = f"contract:{contract_key}"
    edges = data.edges[data.edges["edge_type"].astype(str) == edge_type]
    if edge_type == "PUBLISHED":
        node_ids = edges[edges["target_node_id"].astype(str) == contract_node_id]["source_node_id"]
    else:
        node_ids = edges[edges["source_node_id"].astype(str) == contract_node_id]["target_node_id"]
    return [
        _node_label(data, str(node_id))
        for node_id in node_ids.tolist()
        if _node_label(data, str(node_id))
    ]


def _node_label(data, node_id: str) -> str:
    if data.nodes.empty:
        return ""
    matches = data.nodes[data.nodes["node_id"].astype(str) == node_id]
    if matches.empty:
        return ""
    label = matches.iloc[0].get("label")
    return "" if _is_blank(label) else str(label)


def _row_for_contract(frame, contract_key: str) -> dict[str, Any]:
    if frame.empty or "contract_key_canon" not in frame.columns:
        return {}
    matches = frame[frame["contract_key_canon"].astype(str) == str(contract_key)]
    if matches.empty:
        return {}
    return _clean_record(matches.iloc[0].to_dict())


def _concat_frames(first, second):
    if second.empty:
        return first
    if first.empty:
        return second.copy()
    import pandas as pd

    return pd.concat([first, second], ignore_index=True).drop_duplicates()


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


def _render_missing_artifacts(output_dir: Path, missing: list[Path]) -> None:
    st.error("Faltan artefactos de Agent3 para construir la demo.")
    st.write(f"Carpeta revisada: `{output_dir}`")
    st.dataframe(
        [{"artefacto requerido": str(path)} for path in missing],
        width="stretch",
        hide_index=True,
    )
    st.code(
        "python -c \"from procurewatch.cli import main; raise SystemExit(main(['run-agent3']))\"",
        language="powershell",
    )


def _case_context_contract_key(payload: dict[str, Any]) -> str:
    case_context = _dict_value(payload.get("case_context"))
    value = payload.get("contract_key_canon") or case_context.get("contract_key_canon")
    return "" if _is_blank(value) else str(value)


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in record.items():
        cleaned_value = _clean_value(value)
        if not _is_blank(cleaned_value):
            cleaned[key] = cleaned_value
    return cleaned


def _clean_value(value: object) -> object | None:
    if _is_blank(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (AttributeError, ValueError, TypeError):
            return value
    return value


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    try:
        if value != value:
            return True
    except (TypeError, ValueError):
        return False
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "nat", "none"}


def _first_text(*values: object) -> str:
    for value in values:
        if not _is_blank(value):
            return str(value)
    return ""


def _node_type_label(value: object) -> str:
    return NODE_TYPE_LABELS.get(str(value), str(value))


def _edge_type_label(value: object) -> str:
    return EDGE_TYPE_LABELS.get(str(value), str(value))


def _format_int(value: object) -> str:
    if _is_blank(value):
        return "0"
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def _format_metric(value: object) -> str:
    if _is_blank(value):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _format_percent(value: object) -> str:
    if _is_blank(value):
        return "n/a"
    try:
        return f"{float(value) * 100:.0f} %"
    except (TypeError, ValueError):
        return str(value)


def _format_money(value: object) -> str:
    if _is_blank(value):
        return "n/a"
    try:
        return f"{float(value):,.0f}".replace(",", ".") + " EUR"
    except (TypeError, ValueError):
        return str(value)


def _apply_page_style() -> None:
    st.markdown(
        """
        <style>
        .pw-step {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.75rem;
            min-height: 112px;
            background: #ffffff;
        }
        .pw-step-on {
            border-left: 5px solid #059669;
        }
        .pw-step-off {
            border-left: 5px solid #9ca3af;
            color: #4b5563;
        }
        .pw-step-title {
            font-weight: 700;
            color: #111827;
        }
        .pw-step-state {
            font-size: 0.8rem;
            color: #374151;
            margin: 0.15rem 0 0.35rem;
        }
        .pw-step-text {
            font-size: 0.9rem;
            color: #374151;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
