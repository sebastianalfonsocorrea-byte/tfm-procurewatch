from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

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
    top_communities,
    top_entities,
)
from procurewatch.dashboard_temporal import (  # noqa: E402
    TemporalEvaluation,
    load_temporal_evaluation,
)

DEFAULT_DEMO_DIR = "data/processed/agent3_agent4_demo_2026_06_23"
DEFAULT_TEMPORAL_CANONICAL = "data/processed_sample/agent2_contracts_canonical.parquet"
DEFAULT_TEMPORAL_SCORES = (
    "data/processed_sample/agent2_evaluation/base/agent2_risk_scores.parquet"
)

NODE_TYPE_LABELS = {
    "Buyer": "Comprador publico",
    "Supplier": "Empresa adjudicataria",
    "Contract": "Contrato",
    "CPV": "Categoria CPV",
    "Source": "Fuente de datos",
}

EDGE_TYPE_LABELS = {
    "PUBLISHED": "Publica contrato",
    "AWARDED_TO": "Adjudicado a",
    "HAS_CPV": "Clasificado como",
    "FROM_SOURCE": "Procede de",
}

FLAG_LABELS = {
    "risky_procedure": "Procedimiento con menor publicidad",
    "awarded_above_estimate": "Adjudicacion sobre el valor estimado",
    "missing_supplier": "Proveedor no informado",
    "single_bidder": "Baja concurrencia",
}

FLAG_EXPLANATIONS = {
    "risky_procedure": (
        "El procedimiento reduce publicidad o competencia y eleva la prioridad de revision."
    ),
    "awarded_above_estimate": (
        "El importe adjudicado supera el valor estimado registrado para el contrato."
    ),
    "missing_supplier": "Falta una entidad clave para explicar la adjudicacion.",
    "single_bidder": "La concurrencia limitada puede elevar la prioridad de revision.",
}

RISK_LEVEL_LABELS = {
    "low": "Prioridad baja",
    "medium": "Prioridad media",
    "high": "Prioridad alta",
}

DOCUMENT_TYPE_LABELS = {
    "html": "Pliego o pagina HTML",
    "text": "Documento de texto",
    "pdf": "Documento PDF",
}

SOURCE_LABELS = {
    "synthetic": "Muestra demostrativa",
    "boe": "BOE",
    "place": "PLACE",
    "opentender": "OpenTender",
}

NODE_COLORS = {
    "Buyer": "#2563eb",
    "Supplier": "#059669",
    "Contract": "#7c3aed",
    "CPV": "#d97706",
    "Source": "#475569",
}


@dataclass(frozen=True, slots=True)
class DashboardFilters:
    selected_contract: str
    filtered_contracts: pd.DataFrame
    node_types: set[str]
    relation_types: set[str]
    community_id: int | None
    max_nodes: int
    only_case_neighborhood: bool


def main() -> None:
    st.set_page_config(page_title="ProcureWatch Analytics", layout="wide")
    _apply_page_style()

    output_dir, case_context_path = _render_data_sidebar()
    case_context = _load_case_context(case_context_path) if case_context_path else {}

    missing = missing_demo_artifacts(output_dir)
    if missing:
        _render_missing_artifacts(output_dir, missing)
        return

    data = load_agent3_demo_data(output_dir)
    kpis = build_demo_kpis(data)
    contracts = _build_contract_table(data, case_context)
    temporal, temporal_error, temporal_paths = _load_temporal_data()
    filters = _render_analysis_sidebar(data, contracts, case_context)
    case_view = _build_case_view(data, case_context, filters.selected_contract)

    _render_header()
    _render_decision_strip(case_view)

    (
        summary_tab,
        temporal_tab,
        ranking_tab,
        case_tab,
        network_tab,
        evidence_tab,
        trace_tab,
        method_tab,
    ) = st.tabs(
        [
            "Resumen",
            "Evolucion temporal",
            "Contratos priorizados",
            "Caso seleccionado",
            "Relaciones",
            "Evidencias",
            "Trazabilidad",
            "Metodologia",
        ]
    )
    with summary_tab:
        _render_summary(data, kpis, contracts, case_view)
    with temporal_tab:
        _render_temporal_evolution(temporal, temporal_error, temporal_paths)
    with ranking_tab:
        _render_contract_ranking(filters.filtered_contracts, filters.selected_contract)
    with case_tab:
        _render_case(case_view)
    with network_tab:
        _render_network(data, filters)
    with evidence_tab:
        _render_evidences(case_view)
    with trace_tab:
        _render_traceability(data, case_context, output_dir, case_context_path, case_view)
    with method_tab:
        _render_methodology()


def _render_data_sidebar() -> tuple[Path, Path | None]:
    st.sidebar.header("Demo")
    st.sidebar.caption(
        "Configuracion reproducible. En defensa normalmente no hace falta cambiar estos valores."
    )
    default_output_dir = os.getenv("PROCUREWATCH_AGENT3_DEMO_DIR", DEFAULT_DEMO_DIR)
    output_dir_text = st.sidebar.text_input(
        "Resultados regenerados",
        value=default_output_dir,
        help="Carpeta con los artefactos generados por Agent3.",
    )
    output_dir = Path(output_dir_text)
    default_case_context_path = Path(
        os.getenv(
            "PROCUREWATCH_AGENT4_CASE_CONTEXT",
            str(_default_case_context_path(output_dir)),
        )
    )
    case_context_text = st.sidebar.text_input(
        "Ficha documental del caso",
        value=str(default_case_context_path),
        help="JSON generado por Agent4 para el contrato principal.",
    )
    st.sidebar.markdown(
        """
        <div class="pw-sidebar-note">
            <strong>Modo defensa:</strong> abre primero Resumen y Evolucion temporal; despues
            revisa Caso seleccionado, Relaciones y Evidencias.
        </div>
        """,
        unsafe_allow_html=True,
    )
    return output_dir, Path(case_context_text) if case_context_text else None


def _render_analysis_sidebar(
    data,
    contracts: pd.DataFrame,
    case_context: dict[str, Any],
) -> DashboardFilters:
    st.sidebar.header("Filtros")
    filtered = contracts.copy()

    states = _sorted_text_options(filtered["estado_ficha"].tolist())
    selected_states = st.sidebar.multiselect("Estado del caso", states, default=states)
    if selected_states:
        filtered = filtered[filtered["estado_ficha"].isin(selected_states)]

    buyers = _sorted_text_options(filtered["comprador"].tolist())
    selected_buyers = st.sidebar.multiselect("Comprador", buyers, default=buyers)
    if selected_buyers:
        filtered = filtered[filtered["comprador"].isin(selected_buyers)]

    suppliers = _sorted_text_options(filtered["adjudicatario"].tolist())
    selected_suppliers = st.sidebar.multiselect("Adjudicatario", suppliers, default=suppliers)
    if selected_suppliers:
        filtered = filtered[filtered["adjudicatario"].isin(selected_suppliers)]

    community_options = _community_options(filtered)
    selected_communities = st.sidebar.multiselect(
        "Comunidad de red",
        community_options,
        default=community_options,
    )
    if selected_communities:
        filtered = filtered[filtered["comunidad"].isin(selected_communities)]

    if filtered.empty:
        st.sidebar.warning("Los filtros no dejan contratos visibles; se muestran todos.")
        filtered = contracts.copy()

    preferred_contract = _case_context_contract_key(case_context)
    contract_options = filtered["id_contrato"].tolist()
    if preferred_contract not in contract_options and contract_options:
        preferred_contract = str(contract_options[0])
    contract_index = (
        contract_options.index(preferred_contract)
        if preferred_contract in contract_options
        else 0
    )
    selected_contract = st.sidebar.selectbox(
        "Contrato a explicar",
        contract_options,
        index=contract_index,
        format_func=lambda value: _contract_option_label_from_table(filtered, str(value)),
    )

    st.sidebar.header("Red")
    available_types = sorted(data.entity_metrics["node_type"].dropna().unique().tolist())
    default_types = [item for item in ["Buyer", "Supplier", "Contract"] if item in available_types]
    node_types = st.sidebar.multiselect(
        "Entidades visibles",
        available_types,
        default=default_types,
        format_func=_node_type_label,
    )

    available_relations = sorted(data.edges["edge_type"].dropna().unique().tolist())
    relation_types = st.sidebar.multiselect(
        "Relaciones visibles",
        available_relations,
        default=available_relations,
        format_func=_edge_type_label,
    )

    graph_community_options = ["Todas", *_community_options(contracts)]
    graph_community = st.sidebar.selectbox("Comunidad en el grafo", graph_community_options)
    max_nodes = st.sidebar.slider("Tamano de red", min_value=6, max_value=40, value=18, step=2)
    only_case_neighborhood = st.sidebar.toggle("Solo entorno del contrato", value=True)
    st.sidebar.markdown("#### Capturas recomendadas")
    st.sidebar.caption(
        "Resumen · Evolucion temporal · Caso seleccionado · Relaciones · Evidencias"
    )

    return DashboardFilters(
        selected_contract=str(selected_contract),
        filtered_contracts=filtered,
        node_types=set(node_types),
        relation_types=set(relation_types),
        community_id=None if graph_community == "Todas" else int(graph_community),
        max_nodes=max_nodes,
        only_case_neighborhood=only_case_neighborhood,
    )


def _render_header() -> None:
    st.markdown(
        """
        <section class="pw-hero">
            <div>
                <p class="pw-eyebrow">Demo integrada TFM</p>
                <h1>ProcureWatch Analytics</h1>
                <p class="pw-hero-text">
                    Priorizacion explicable de contratos publicos combinando scoring,
                    relaciones de red y evidencia documental trazable.
                </p>
            </div>
            <div class="pw-hero-badge">Revision humana, no veredicto de fraude</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="pw-callout">
            <strong>Que estas viendo:</strong> la demo sintetica/offline reconstruye el caso
            <code>PW-2024-0001</code>. La pestana Evolucion temporal usa, de forma separada, la
            evaluacion real de Agent2 sobre 3.437 contratos para mostrar volumen y riesgo por mes.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "El sistema ayuda a priorizar revision humana y no declara fraude; las evidencias sirven "
        "para explicar por que un caso merece ser revisado."
    )


def _render_decision_strip(case_view: dict[str, Any]) -> None:
    priority = _risk_level_label(case_view.get("risk_level"))
    score = _format_score(case_view.get("risk_score"))
    flags = len(case_view.get("red_flags", []))
    evidences = len(case_view.get("evidences", []))

    columns = st.columns([1.25, 1, 1, 1])
    columns[0].metric("Contrato seleccionado", case_view.get("contract_key") or "Sin contrato")
    columns[1].metric("Prioridad", priority)
    columns[2].metric("Score Agent2", score)
    columns[3].metric("Evidencias Agent4", str(evidences))

    if flags:
        st.markdown(
            f"""
            <div class="pw-reading">
                <strong>Lectura principal:</strong> {priority.lower()} con {flags} senales
                explicables y {evidences} evidencias documentales asociadas. Esta salida ayuda a
                decidir que revisar primero; no prueba fraude ni sustituye auditoria.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="pw-reading">
                <strong>Lectura principal:</strong> el contrato tiene metricas relacionales, pero
                la ficha cargada no contiene scoring documental completo para este caso.
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_summary(
    data,
    kpis: dict[str, int],
    contracts: pd.DataFrame,
    case_view: dict[str, Any],
) -> None:
    st.subheader("Resumen ejecutivo")
    st.write(
        "Esta vista resume la demo de extremo a extremo. La idea es que el tribunal pueda seguir "
        "el camino del dato sin abrir codigo: contrato canonico, prioridad Agent2, grafo Agent3, "
        "evidencia Agent4 y trazabilidad final."
    )
    _render_kpis(kpis, contracts, case_view)
    _render_agent_flow(case_view)

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### Contratos con mayor interes de revision")
        st.caption(
            "Ordenados por una combinacion de score Agent2, senales relacionales y disponibilidad "
            "de ficha documental."
        )
        ranking = _display_contract_columns(contracts).head(5)
        st.dataframe(ranking, width="stretch", hide_index=True)
    with right:
        st.markdown("#### Caso activo")
        _render_case_snapshot(case_view)

    st.subheader("Distribucion del lote de demo")
    _render_distribution_charts(data, contracts)


def _load_temporal_data(
) -> tuple[TemporalEvaluation | None, str | None, tuple[Path, Path]]:
    canonical_path = Path(
        os.getenv("PROCUREWATCH_AGENT2_TEMPORAL_CANONICAL", DEFAULT_TEMPORAL_CANONICAL)
    )
    scores_path = Path(os.getenv("PROCUREWATCH_AGENT2_TEMPORAL_SCORES", DEFAULT_TEMPORAL_SCORES))
    try:
        temporal = load_temporal_evaluation(canonical_path, scores_path)
    except (FileNotFoundError, ValueError, OSError) as exc:
        return None, str(exc), (canonical_path, scores_path)
    return temporal, None, (canonical_path, scores_path)


def _render_temporal_evolution(
    temporal: TemporalEvaluation | None,
    error: str | None,
    paths: tuple[Path, Path],
) -> None:
    st.subheader("Evolucion temporal de contratos y riesgo")
    st.write(
        "Esta vista cruza el canonico evaluado con los scores base de Agent2. Las barras muestran "
        "contratos con fecha de publicacion valida y la linea representa el riesgo medio mensual "
        "en escala 0-100. No se imputan fechas ausentes."
    )
    if temporal is None:
        st.warning(
            "La serie temporal no esta disponible. Comprueba los artefactos de Agent2. "
            f"Detalle: {error or 'error no especificado'}"
        )
        st.caption(f"Canonico: `{paths[0]}` · Scores: `{paths[1]}`")
        return
    if temporal.monthly.empty:
        st.info("No hay contratos con fecha de publicacion y score validos para representar.")
        return

    columns = st.columns(4)
    columns[0].metric("Contratos evaluados", _format_int(temporal.evaluated_contracts))
    columns[1].metric("Con fecha valida", _format_int(temporal.dated_contracts))
    columns[2].metric("Meses cubiertos", _format_int(temporal.month_count))
    columns[3].metric("Fechas no validas", _format_int(temporal.invalid_date_contracts))

    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=temporal.monthly["month"],
            y=temporal.monthly["contracts"],
            name="Contratos publicados",
            marker_color="#2563eb",
            hovertemplate="%{x|%b %Y}<br>Contratos: %{y}<extra></extra>",
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=temporal.monthly["month"],
            y=temporal.monthly["mean_risk_score"],
            name="Riesgo medio Agent2",
            mode="lines+markers",
            line={"color": "#d97706", "width": 3},
            marker={"size": 6},
            hovertemplate="%{x|%b %Y}<br>Riesgo medio: %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )
    figure.update_layout(
        height=480,
        margin={"l": 20, "r": 20, "t": 35, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        hovermode="x unified",
        bargap=0.18,
    )
    figure.update_xaxes(title_text="Mes de publicacion", tickformat="%b\n%Y")
    figure.update_yaxes(title_text="Contratos", rangemode="tozero", secondary_y=False)
    figure.update_yaxes(
        title_text="Riesgo medio Agent2 (0-100)",
        range=[0, 100],
        secondary_y=True,
    )
    st.plotly_chart(figure, width="stretch")
    st.caption(
        "Serie calculada sobre los artefactos versionados de la evaluacion base de Agent2. "
        f"Se excluyen {temporal.invalid_date_contracts} contratos sin fecha de publicacion valida"
        f" y {temporal.invalid_score_contracts} sin score numerico."
    )


def _render_kpis(
    kpis: dict[str, int],
    contracts: pd.DataFrame,
    case_view: dict[str, Any],
) -> None:
    buyer_count = contracts["comprador"].nunique()
    supplier_count = contracts["adjudicatario"].nunique()
    evidence_count = len(case_view.get("evidences", []))
    labels = [
        ("Contratos analizados", kpis.get("contracts", 0)),
        ("Compradores", buyer_count),
        ("Adjudicatarios", supplier_count),
        ("Relaciones de red", kpis.get("edges", 0)),
        ("Comunidades", kpis.get("communities", 0)),
        ("Evidencias del caso", evidence_count),
    ]
    columns = st.columns(len(labels))
    for column, (label, value) in zip(columns, labels, strict=False):
        column.metric(label, _format_int(value))
    st.caption(
        "Los KPIs proceden de los artefactos regenerados por `run-integrated-demo`; la muestra es "
        "pequena y sintetica para defensa reproducible."
    )


def _render_agent_flow(case_view: dict[str, Any]) -> None:
    has_agent2 = not _is_blank(case_view.get("risk_score"))
    has_agent3 = bool(case_view.get("agent3_metrics"))
    has_agent4 = bool(case_view.get("evidences"))
    items = [
        ("Agent1", "Normaliza contratos y conserva trazabilidad de fuente", True),
        ("Agent2", "Calcula prioridad y red flags explicables", has_agent2),
        ("Agent3", "Construye red, comunidades y metricas relacionales", has_agent3),
        ("Agent4", "Recupera evidencia documental y citas", has_agent4),
    ]
    columns = st.columns(len(items))
    for column, (title, detail, active) in zip(columns, items, strict=False):
        state = "Disponible" if active else "No disponible para este caso"
        css_class = "pw-step-on" if active else "pw-step-off"
        column.markdown(
            f"""
            <div class="pw-step {css_class}">
                <div class="pw-step-title">{title}</div>
                <div class="pw-step-state">{state}</div>
                <div class="pw-step-text">{detail}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_distribution_charts(data, contracts: pd.DataFrame) -> None:
    left, right = st.columns(2)
    with left:
        node_counts = node_type_counts(data)
        if node_counts.empty:
            st.info("No hay entidades para representar.")
        else:
            node_counts = node_counts.copy()
            node_counts["Tipo de entidad"] = node_counts["node_type"].map(_node_type_label)
            st.plotly_chart(
                px.bar(
                    node_counts,
                    x="Tipo de entidad",
                    y="nodes",
                    color="Tipo de entidad",
                    labels={"nodes": "Total"},
                    color_discrete_sequence=["#2563eb", "#059669", "#7c3aed", "#d97706"],
                ),
                width="stretch",
            )
            st.caption("Cada barra representa un tipo de nodo construido por Agent3.")
    with right:
        edge_counts = edge_type_counts(data)
        if edge_counts.empty:
            st.info("No hay relaciones para representar.")
        else:
            edge_counts = edge_counts.copy()
            edge_counts["Tipo de relacion"] = edge_counts["edge_type"].map(_edge_type_label)
            st.plotly_chart(
                px.bar(
                    edge_counts,
                    x="Tipo de relacion",
                    y="edges",
                    color="Tipo de relacion",
                    labels={"edges": "Total"},
                    color_discrete_sequence=["#0f766e", "#9333ea", "#b45309", "#475569"],
                ),
                width="stretch",
            )
            st.caption("Las relaciones explican como se conectan compradores, contratos y fuentes.")

    left, right = st.columns(2)
    with left:
        communities = top_communities(data, limit=12)
        if communities.empty:
            st.info("No hay comunidades calculadas.")
        else:
            chart = communities.rename(
                columns={
                    "community_id": "Comunidad",
                    "contract_count": "Contratos",
                    "node_count": "Entidades",
                    "buyer_count": "Compradores",
                    "supplier_count": "Adjudicatarios",
                }
            )
            st.plotly_chart(
                px.bar(
                    chart,
                    x="Comunidad",
                    y="Contratos",
                    color="Entidades",
                    hover_data=["Compradores", "Adjudicatarios"],
                    color_continuous_scale="Teal",
                ),
                width="stretch",
            )
            st.caption("Las comunidades agrupan entidades conectadas dentro del grafo.")
    with right:
        st.markdown("#### Compradores y adjudicatarios")
        compact = contracts[["comprador", "adjudicatario", "id_contrato"]].rename(
            columns={
                "comprador": "Comprador",
                "adjudicatario": "Adjudicatario",
                "id_contrato": "Contrato",
            }
        )
        st.dataframe(compact, width="stretch", hide_index=True)


def _render_top_case_cards(contracts: pd.DataFrame, selected_contract: str) -> None:
    top_cases = contracts.head(3).to_dict("records")
    if not top_cases:
        return
    columns = st.columns(len(top_cases))
    for column, row in zip(columns, top_cases, strict=False):
        selected = row.get("id_contrato") == selected_contract
        css_class = "pw-case-card pw-case-card-selected" if selected else "pw-case-card"
        priority = row.get("prioridad", "n/a")
        reason = row.get("motivo_revision", "n/a")
        column.markdown(
            f"""
            <div class="{css_class}">
                <div class="pw-card-kicker">{'Caso activo' if selected else 'Caso priorizado'}</div>
                <div class="pw-card-title">{row.get('id_contrato', 'n/a')}</div>
                <div class="pw-card-subtitle">{row.get('titulo', 'Sin titulo')}</div>
                <div class="pw-card-line"><strong>Prioridad:</strong> {priority}</div>
                <div class="pw-card-line"><strong>Motivo:</strong> {reason}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_contract_ranking(contracts: pd.DataFrame, selected_contract: str) -> None:
    st.subheader("Contratos priorizados")
    st.write(
        "La tabla combina score Agent2, senales relacionales de Agent3 y cobertura documental de "
        "Agent4. Es una cola de revision, no una lista de fraude."
    )
    _render_top_case_cards(contracts, selected_contract)

    display = _display_contract_columns(contracts)
    display.insert(
        0,
        "Seleccionado",
        ["si" if key == selected_contract else "" for key in contracts["id_contrato"]],
    )
    st.dataframe(display, width="stretch", hide_index=True)

    st.markdown("#### Lectura de senales")
    st.caption(
        "Estas columnas muestran por que un contrato sube en prioridad: recurrencia, peso de la "
        "relacion e importancia en la red."
    )
    signal_rows = contracts[
        [
            "id_contrato",
            "motivo_revision",
            "recurrencia_comprador_proveedor",
            "peso_relacion",
            "importancia_red",
            "tamano_comunidad",
        ]
    ].rename(
        columns={
            "id_contrato": "Contrato",
            "motivo_revision": "Motivo principal",
            "recurrencia_comprador_proveedor": "Contratos comprador-proveedor",
            "peso_relacion": "Peso de esa relacion",
            "importancia_red": "Importancia en la red",
            "tamano_comunidad": "Entidades en comunidad",
        }
    )
    signal_rows["Peso de esa relacion"] = signal_rows["Peso de esa relacion"].map(_format_percent)
    signal_rows["Importancia en la red"] = signal_rows["Importancia en la red"].map(_format_metric)
    st.dataframe(signal_rows, width="stretch", hide_index=True)


def _render_case(case_view: dict[str, Any]) -> None:
    st.subheader("Caso seleccionado")
    if not case_view.get("contract_key"):
        st.warning("No hay contrato seleccionado.")
        return

    if case_view.get("case_context_contract") and not case_view.get("case_context_matches"):
        st.warning(
            "La ficha documental cargada corresponde a "
            f"{case_view['case_context_contract']}. Para este contrato se muestran solo "
            "datos canonicos y metricas de red."
        )

    columns = st.columns(4)
    columns[0].metric("Prioridad Agent2", _risk_level_label(case_view.get("risk_level")))
    columns[1].metric("Puntuacion", _format_score(case_view.get("risk_score")))
    columns[2].metric("Red flags", str(len(case_view.get("red_flags", []))))
    columns[3].metric("Relaciones del contrato", _format_metric(case_view.get("contract_links")))

    _render_case_explainer(case_view)
    _render_case_review_plan(case_view)

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("#### Identificacion")
        st.dataframe(_contract_context_rows(case_view), width="stretch", hide_index=True)
    with right:
        st.markdown("#### Lectura ejecutiva")
        _render_case_snapshot(case_view)
        summary = case_view.get("summary")
        if summary:
            st.write(str(summary))

    left, right = st.columns(2)
    with left:
        st.markdown("#### Senales de riesgo")
        rows = _agent2_signal_rows(case_view)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("No hay red flags Agent2 cargadas para este contrato.")
    with right:
        st.markdown("#### Senales relacionales")
        rows = _agent3_signal_rows(case_view)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("No hay metricas relacionales disponibles para este contrato.")

    warnings = case_view.get("warnings", [])
    if warnings:
        st.warning("\n".join(f"- {item}" for item in warnings))


def _render_case_explainer(case_view: dict[str, Any]) -> None:
    flags = _flag_list_label(case_view.get("red_flags", []))
    metrics = _dict_value(case_view.get("agent3_metrics"))
    recurrence = _format_metric(metrics.get("buyer_supplier_recurrence"))
    share = _format_percent(metrics.get("buyer_supplier_contract_share"))
    evidences = len(case_view.get("evidences", []))
    st.markdown(
        f"""
        <div class="pw-case-explainer">
            <div>
                <span class="pw-badge">Agent2</span>
                <strong>{flags}</strong>
                <p>Reglas deterministas convierten datos del contrato en prioridad de revision.</p>
            </div>
            <div>
                <span class="pw-badge">Agent3</span>
                <strong>{recurrence} contratos comprador-proveedor; peso {share}</strong>
                <p>La red muestra recurrencia, comunidad y posicion del contrato.</p>
            </div>
            <div>
                <span class="pw-badge">Agent4</span>
                <strong>{evidences} evidencias citadas</strong>
                <p>Los documentos recuperados apoyan la explicacion sin emitir veredicto.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_case_review_plan(case_view: dict[str, Any]) -> None:
    actions = _case_review_plan(case_view)
    st.markdown("#### Plan de revision del caso")
    st.caption(
        "Secuencia sugerida para analizar el expediente con las senales disponibles. Es una "
        "priorizacion operativa, no una conclusion juridica."
    )
    columns = st.columns(len(actions))
    for column, action in zip(columns, actions, strict=False):
        column.markdown(
            f"""
            <div class="pw-review-step">
                <strong>{action['title']}</strong>
                <p>{action['text']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _case_review_plan(case_view: dict[str, Any]) -> list[dict[str, str]]:
    actions = [
        {
            "title": "Procedimiento",
            "text": "Contrastar el tipo de procedimiento con el objeto, importe y justificacion.",
        },
        {
            "title": "Importe",
            "text": "Revisar la relacion entre valor estimado, adjudicacion y desviaciones.",
        },
        {
            "title": "Relacion",
            "text": "Analizar recurrencia comprador-adjudicatario y posicion en la comunidad.",
        },
    ]
    if case_view.get("evidences"):
        actions.append(
            {
                "title": "Documentos",
                "text": "Verificar evidencias recuperadas, citas y trazabilidad documental.",
            }
        )
    return actions[:4]


def _render_case_snapshot(case_view: dict[str, Any]) -> None:
    fields = [
        ("Contrato", case_view.get("contract_key")),
        ("Titulo", case_view.get("title")),
        ("Comprador", case_view.get("buyer_name")),
        ("Adjudicatario", case_view.get("supplier_name")),
        ("Procedimiento", case_view.get("procedure")),
        ("Importe estimado", _format_money(case_view.get("estimated_value"))),
        ("Importe adjudicado", _format_money(case_view.get("awarded_value"))),
    ]
    for label, value in fields:
        if not _is_blank(value):
            st.write(f"**{label}:** {value}")


def _render_network(data, filters: DashboardFilters) -> None:
    st.subheader("Mapa de relaciones")
    st.write(
        "Agent3 convierte contratos, compradores, adjudicatarios, CPV y fuentes en una red. El "
        "contrato seleccionado se destaca para ver su entorno inmediato."
    )
    nodes, edges = _network_frames(data, filters)
    if nodes.empty:
        st.warning("No hay entidades para el filtro actual.")
        return

    _render_network_summary(nodes, edges, filters.selected_contract)

    left, right = st.columns([1.6, 1])
    with left:
        st.plotly_chart(
            _network_figure(nodes, edges, focus_contract=filters.selected_contract),
            width="stretch",
        )
        st.caption(
            "Colores por tipo de entidad. El nodo grande y bordeado corresponde al contrato "
            "seleccionado."
        )
    with right:
        st.markdown("#### Entidades visibles")
        st.dataframe(_network_node_table(nodes), width="stretch", hide_index=True)

    st.markdown("#### Relaciones visibles")
    relation_table = _network_edge_table(data, edges)
    if relation_table.empty:
        st.info("No hay relaciones visibles con los filtros actuales.")
    else:
        st.dataframe(relation_table, width="stretch", hide_index=True)

    st.markdown("#### Entidades con mas peso en la red")
    left, right = st.columns(2)
    with left:
        _render_entity_table(data, node_type="Buyer", title="Compradores principales")
    with right:
        _render_entity_table(data, node_type="Supplier", title="Adjudicatarios principales")


def _network_frames(data, filters: DashboardFilters) -> tuple[pd.DataFrame, pd.DataFrame]:
    if filters.only_case_neighborhood:
        nodes, edges = _contract_neighborhood(data, filters.selected_contract)
    else:
        nodes, edges = build_demo_subgraph(
            data,
            max_nodes=filters.max_nodes,
            node_types=filters.node_types if filters.node_types else None,
            community_id=filters.community_id,
        )
        nodes, edges = _ensure_focus_contract(data, nodes, edges, filters.selected_contract)

    if filters.node_types:
        nodes = nodes[nodes["node_type"].isin(filters.node_types)].copy()
    if filters.relation_types:
        edges = edges[edges["edge_type"].isin(filters.relation_types)].copy()

    node_ids = set(nodes["node_id"].astype(str))
    edges = edges[
        edges["source_node_id"].astype(str).isin(node_ids)
        & edges["target_node_id"].astype(str).isin(node_ids)
    ].copy()
    if len(nodes) > filters.max_nodes:
        nodes = nodes.sort_values(
            by=["betweenness_centrality", "neighbor_count", "node_id"],
            ascending=[False, False, True],
        ).head(filters.max_nodes)
        node_ids = set(nodes["node_id"].astype(str))
        edges = edges[
            edges["source_node_id"].astype(str).isin(node_ids)
            & edges["target_node_id"].astype(str).isin(node_ids)
        ].copy()
    return nodes, edges


def _render_network_summary(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    selected_contract: str,
) -> None:
    node_types = nodes["node_type"].astype(str).value_counts().to_dict()
    summary = [
        f"{len(nodes)} entidades visibles",
        f"{len(edges)} relaciones",
        f"contrato foco {selected_contract}",
    ]
    type_text = ", ".join(
        f"{_node_type_label(node_type)}: {count}" for node_type, count in node_types.items()
    )
    st.markdown(
        f"""
        <div class="pw-callout">
            <strong>Lectura del grafo:</strong> {'; '.join(summary)}.
            <br><span>{type_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _contract_neighborhood(data, contract_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    focus_id = f"contract:{contract_key}"
    edges = data.edges[
        (data.edges["source_node_id"].astype(str) == focus_id)
        | (data.edges["target_node_id"].astype(str) == focus_id)
    ].copy()
    node_ids = {focus_id}
    node_ids.update(edges["source_node_id"].astype(str).tolist())
    node_ids.update(edges["target_node_id"].astype(str).tolist())
    nodes = data.entity_metrics[data.entity_metrics["node_id"].astype(str).isin(node_ids)].copy()
    return nodes, edges


def _network_figure(nodes: pd.DataFrame, edges: pd.DataFrame, *, focus_contract: str) -> go.Figure:
    graph = nx.Graph()
    labels = dict(zip(nodes["node_id"], nodes["label"], strict=False))
    node_types = dict(zip(nodes["node_id"], nodes["node_type"], strict=False))
    communities = dict(zip(nodes["node_id"], nodes["community_id"], strict=False))
    neighbors = dict(zip(nodes["node_id"], nodes["neighbor_count"], strict=False))
    focus_node_id = f"contract:{focus_contract}"

    for node_id in nodes["node_id"].astype(str):
        graph.add_node(node_id)
    for row in edges.to_dict("records"):
        graph.add_edge(str(row["source_node_id"]), str(row["target_node_id"]))
    positions = nx.spring_layout(graph, seed=42, k=0.8) if graph.number_of_nodes() else {}

    figure = go.Figure()
    edge_x = []
    edge_y = []
    for source, target in graph.edges:
        source_x, source_y = positions[source]
        target_x, target_y = positions[target]
        edge_x.extend([source_x, target_x, None])
        edge_y.extend([source_y, target_y, None])
    figure.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"width": 1.2, "color": "#cbd5e1"},
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
            hover.append(
                "<br>".join(
                    [
                        f"<b>{labels.get(node_id, node_id)}</b>",
                        _node_type_label(node_type),
                        f"Comunidad: {_format_metric(communities.get(node_id))}",
                        f"Conexiones: {_format_metric(neighbors.get(node_id))}",
                    ]
                )
            )
            sizes.append(24 if node_id == focus_node_id else 13)
            line_widths.append(4 if node_id == focus_node_id else 1)
        figure.add_trace(
            go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers",
                marker={
                    "size": sizes,
                    "color": NODE_COLORS.get(str(node_type), "#111827"),
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
        paper_bgcolor="white",
    )
    return figure


def _network_node_table(nodes: pd.DataFrame) -> pd.DataFrame:
    if nodes.empty:
        return pd.DataFrame()
    table = nodes[
        ["label", "node_type", "neighbor_count", "betweenness_centrality", "community_id"]
    ].copy()
    table["node_type"] = table["node_type"].map(_node_type_label)
    table["betweenness_centrality"] = table["betweenness_centrality"].map(_format_metric)
    return table.rename(
        columns={
            "label": "Entidad",
            "node_type": "Tipo",
            "neighbor_count": "Conexiones",
            "betweenness_centrality": "Importancia en red",
            "community_id": "Comunidad",
        }
    )


def _network_edge_table(data, edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return pd.DataFrame()
    table = edges[["edge_type", "contract_key_canon", "source_node_id", "target_node_id"]].copy()
    table["edge_type"] = table["edge_type"].map(_edge_type_label)
    table["source_node_id"] = table["source_node_id"].map(
        lambda value: _node_label(data, str(value))
    )
    table["target_node_id"] = table["target_node_id"].map(
        lambda value: _node_label(data, str(value))
    )
    return table.rename(
        columns={
            "edge_type": "Relacion",
            "contract_key_canon": "Contrato asociado",
            "source_node_id": "Origen",
            "target_node_id": "Destino",
        }
    )


def _render_entity_table(data, *, node_type: str, title: str) -> None:
    st.markdown(f"#### {title}")
    entities = top_entities(data, node_type=node_type, limit=10)
    if entities.empty:
        st.info("No hay entidades disponibles.")
        return
    table = entities[["label", "neighbor_count", "betweenness_centrality", "community_id"]].copy()
    table["betweenness_centrality"] = table["betweenness_centrality"].map(_format_metric)
    table = table.rename(
        columns={
            "label": "Entidad",
            "neighbor_count": "Conexiones",
            "betweenness_centrality": "Importancia en red",
            "community_id": "Comunidad",
        }
    )
    st.dataframe(table, width="stretch", hide_index=True)


def _render_evidences(case_view: dict[str, Any]) -> None:
    st.subheader("Evidencias documentales")
    if case_view.get("case_context_contract") and not case_view.get("case_context_matches"):
        st.warning(
            "La ficha documental cargada pertenece a otro contrato. Para este caso solo se "
            "muestran datos de red."
        )
        return

    evidences = case_view.get("evidences", [])
    citations = case_view.get("citations", [])
    if not evidences:
        st.info(
            "No hay evidencia documental recuperada para este contrato. La salida debe indicar "
            "esa ausencia y no completar conclusiones por inferencia."
        )
        return

    st.write(
        "Agent4 recupera fragmentos documentales relacionados con el contrato. Cada evidencia "
        "mantiene identificadores para poder rastrear de que documento y chunk sale."
    )
    for index, evidence in enumerate(evidences, start=1):
        with st.container(border=True):
            st.markdown(f"#### Evidencia documental {index}")
            left, right = st.columns([1, 2])
            with left:
                document_type = _document_type_label(evidence.get("document_type"))
                source = _source_label(evidence.get("source"))
                contract_key = evidence.get("contract_key_canon", "n/a")
                relevance = _format_score(evidence.get("score"))
                st.markdown(
                    f"""
                    <div class="pw-mini-card">
                        <div><strong>Tipo:</strong> {document_type}</div>
                        <div><strong>Fuente:</strong> {source}</div>
                        <div><strong>Contrato:</strong> {contract_key}</div>
                        <div><strong>Relevancia:</strong> {relevance}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with right:
                st.markdown("**Extracto recuperado**")
                st.write(str(evidence.get("text_excerpt") or "Sin extracto disponible."))
                with st.expander("Identificadores trazables", expanded=False):
                    st.write(f"document_id: `{evidence.get('document_id', 'n/a')}`")
                    st.write(f"chunk_id: `{evidence.get('chunk_id', 'n/a')}`")

    st.markdown("#### Citas")
    if citations:
        st.dataframe(
            [{"Cita trazable": citation} for citation in citations],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No hay citas documentales asociadas.")


def _render_traceability(
    data,
    case_context: dict[str, Any],
    output_dir: Path,
    case_context_path: Path | None,
    case_view: dict[str, Any],
) -> None:
    st.subheader("Trazabilidad y reproduccion")
    st.write(
        "Esta vista mantiene la parte tecnica en un sitio separado para no ensuciar la narrativa "
        "principal. Aqui se ve como reproducir la demo y que artefactos alimentan cada vista."
    )
    st.download_button(
        "Descargar resumen Markdown del caso",
        data=_case_markdown_summary(case_view),
        file_name=f"procurewatch_{case_view.get('contract_key', 'caso')}_resumen.md",
        mime="text/markdown",
    )

    st.markdown("#### Comandos reproducibles")
    st.code(
        "\n".join(
            [
                "$env:PYTHONPATH='scr'; python -m procurewatch.cli run-integrated-demo",
                "$env:PYTHONPATH='scr'; python -m procurewatch.cli validate-dashboard-demo",
                "streamlit run frontend/agent3_demo.py",
            ]
        ),
        language="powershell",
    )

    outputs = data.report.get("outputs", {})
    output_rows = [
        {"Artefacto": _artifact_label(name), "Ruta": path} for name, path in outputs.items()
    ]
    st.dataframe(output_rows, width="stretch", hide_index=True)

    left, right = st.columns(2)
    with left:
        with st.expander("Rutas cargadas", expanded=False):
            st.write(f"Carpeta Agent3: `{output_dir}`")
            st.write(f"Ficha Agent4: `{case_context_path}`")
        with st.expander("Resumen de red Agent3", expanded=False):
            st.json(data.network_summary)
    with right:
        with st.expander("Metricas del contrato seleccionado", expanded=False):
            st.json(case_view.get("agent3_metrics", {}))
        with st.expander("Payload Agent4 completo", expanded=False):
            if case_context:
                st.json(case_context)
            else:
                st.info("No hay payload Agent4 cargado.")


def _case_markdown_summary(case_view: dict[str, Any]) -> str:
    flags = _flag_list_label(case_view.get("red_flags", []))
    metrics = _dict_value(case_view.get("agent3_metrics"))
    evidences = _list_value(case_view.get("evidences"))
    lines = [
        "# Resumen ProcureWatch",
        "",
        f"- Contrato: {case_view.get('contract_key', 'n/a')}",
        f"- Objeto: {case_view.get('title', 'n/a')}",
        f"- Comprador: {case_view.get('buyer_name', 'n/a')}",
        f"- Adjudicatario: {case_view.get('supplier_name', 'n/a')}",
        f"- Prioridad Agent2: {_risk_level_label(case_view.get('risk_level'))}",
        f"- Score Agent2: {_format_score(case_view.get('risk_score'))}",
        f"- Red flags: {flags}",
        "",
        "## Lectura Agent3",
        "",
        "- Recurrencia comprador-proveedor: "
        f"{_format_metric(metrics.get('buyer_supplier_recurrence'))}",
        f"- Peso de la relacion: {_format_percent(metrics.get('buyer_supplier_contract_share'))}",
        f"- Comunidad: {_format_metric(metrics.get('community_id'))}",
        f"- Importancia en red: {_format_metric(metrics.get('contract_betweenness_centrality'))}",
        "",
        "## Evidencias Agent4",
        "",
    ]
    if evidences:
        for index, evidence in enumerate(evidences, start=1):
            lines.extend(
                [
                    f"{index}. {evidence.get('text_excerpt', 'Sin extracto disponible.')}",
                    f"   - document_id: {evidence.get('document_id', 'n/a')}",
                    f"   - chunk_id: {evidence.get('chunk_id', 'n/a')}",
                ]
            )
    else:
        lines.append("- No hay evidencias documentales cargadas para este caso.")
    lines.extend(
        [
            "",
            "## Frontera metodologica",
            "",
            "ProcureWatch prioriza revision humana. No declara fraude, no sustituye una auditoria "
            "y no representa una plataforma productiva.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_methodology() -> None:
    st.subheader("Metodologia de la demo")
    st.write(
        "ProcureWatch organiza el analisis como una cadena de agentes. Cada bloque produce una "
        "salida trazable que alimenta la siguiente vista del dashboard."
    )
    rows = [
        {
            "Bloque": "Agent1",
            "Que aporta": "Contrato canonico y trazabilidad de fuente.",
            "Donde se ve": "Identificacion del caso y trazabilidad.",
        },
        {
            "Bloque": "Agent2",
            "Que aporta": "Score, prioridad y red flags deterministas.",
            "Donde se ve": "Resumen, ranking y caso seleccionado.",
        },
        {
            "Bloque": "Agent3",
            "Que aporta": "Grafo, comunidades y metricas relacionales.",
            "Donde se ve": "Relaciones y senales relacionales.",
        },
        {
            "Bloque": "Agent4",
            "Que aporta": "Evidencias documentales, citas y warnings.",
            "Donde se ve": "Evidencias y ficha del caso.",
        },
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.markdown(
        """
        <div class="pw-callout">
            <strong>Frontera metodologica:</strong> la demo prioriza revision humana. No declara
            fraude, no sustituye una auditoria y no representa una plataforma productiva.
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        st.markdown("#### Implementado en el MVP")
        st.markdown(
            """
            - Demo integrada offline regenerable.
            - Evolucion temporal sobre la evaluacion real de Agent2.
            - Ranking de contratos y ficha explicable.
            - Red de relaciones comprador-proveedor-contrato.
            - Evidencias documentales con citas trazables.
            - Validacion headless del dashboard.
            """
        )
    with right:
        st.markdown("#### Limitaciones declaradas")
        st.markdown(
            """
            - Muestra sintetica reducida para defensa reproducible.
            - La serie temporal excluye fechas ausentes sin imputarlas.
            - Matching BOE/PLACE/OpenTender todavia imperfecto.
            - Servicios PostgreSQL, Neo4j, Qdrant y Ollama opcionales.
            - Agent4 no descarga pliegos PLACSP ni ejecuta crawling vivo.
            """
        )


def _build_contract_table(data, payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    context_contract = _case_context_contract_key(payload)
    for contract_key in _contract_options(data):
        feature_row = _row_for_contract(data.agent2_features, contract_key)
        contract_row = _contract_node_record(data, contract_key)
        score = _agent2_score_for_contract(payload, contract_key)
        red_flags = _list_value(score.get("red_flags"))
        recurrence = feature_row.get("buyer_supplier_recurrence")
        share = feature_row.get("buyer_supplier_contract_share")
        centrality = feature_row.get("contract_betweenness_centrality")
        community_size = feature_row.get("community_size")
        title = _first_text(contract_row.get("contract_title"), contract_key)
        buyer_name = _first_text(
            _connected_node_label(data, contract_key, edge_type="PUBLISHED"),
            "No informado",
        )
        supplier_name = _first_text(
            _connected_node_label(data, contract_key, edge_type="AWARDED_TO"),
            "No informado",
        )
        has_context = bool(context_contract and context_contract == contract_key)
        rows.append(
            {
                "id_contrato": contract_key,
                "contrato": f"{contract_key} - {title}",
                "titulo": title,
                "comprador": buyer_name,
                "adjudicatario": supplier_name,
                "prioridad": _risk_level_label(score.get("risk_level")),
                "puntuacion": score.get("risk_score"),
                "red_flags": len(red_flags),
                "senales": _flag_list_label(red_flags),
                "estado_ficha": "Ficha completa" if has_context else "Solo red de relaciones",
                "comunidad": str(int(feature_row.get("community_id", 0))),
                "recurrencia_comprador_proveedor": recurrence,
                "peso_relacion": share,
                "importancia_red": centrality,
                "tamano_comunidad": community_size,
                "cpv": feature_row.get("cpv_count"),
                "motivo_revision": _review_reason(red_flags, recurrence, share, centrality),
                "ranking": _ranking_score(score, recurrence, share, centrality, has_context),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(
        by=["ranking", "red_flags", "importancia_red", "id_contrato"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def _display_contract_columns(contracts: pd.DataFrame) -> pd.DataFrame:
    display = contracts[
        [
            "id_contrato",
            "titulo",
            "comprador",
            "adjudicatario",
            "prioridad",
            "puntuacion",
            "red_flags",
            "estado_ficha",
            "motivo_revision",
        ]
    ].copy()
    display["puntuacion"] = display["puntuacion"].map(_format_score)
    return display.rename(
        columns={
            "id_contrato": "ID del contrato",
            "titulo": "Objeto",
            "comprador": "Comprador",
            "adjudicatario": "Adjudicatario",
            "prioridad": "Prioridad",
            "puntuacion": "Puntuacion",
            "red_flags": "Red flags",
            "estado_ficha": "Cobertura demo",
            "motivo_revision": "Motivo principal",
        }
    )


def _build_case_view(data, payload: dict[str, Any], selected_contract: str) -> dict[str, Any]:
    case_context = _dict_value(payload.get("case_context"))
    case_context_contract = _case_context_contract_key(payload)
    context_matches = bool(case_context_contract and case_context_contract == selected_contract)
    matched_context = case_context if context_matches else {}
    agent2_score = _agent2_score_for_contract(payload, selected_contract)

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
        "source": _source_label(
            _first_text(contract_fields.get("source"), feature_row.get("source"))
        ),
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
        "contract_links": feature_row.get("contract_neighbor_count"),
    }


def _contract_context_rows(case_view: dict[str, Any]) -> list[dict[str, str]]:
    rows = [
        ("ID del contrato", case_view.get("contract_key")),
        ("Objeto", case_view.get("title")),
        ("Comprador", case_view.get("buyer_name")),
        ("Adjudicatario", case_view.get("supplier_name")),
        ("Procedimiento", case_view.get("procedure")),
        ("Valor estimado", _format_money(case_view.get("estimated_value"))),
        ("Valor adjudicado", _format_money(case_view.get("awarded_value"))),
        ("Codigos CPV", case_view.get("cpv_codes")),
        ("Fecha de publicacion", case_view.get("publication_date")),
        ("Fecha de adjudicacion", case_view.get("award_date")),
        ("Fuente", case_view.get("source")),
        ("Registro de origen", case_view.get("source_record_id")),
    ]
    return [{"Campo": label, "Valor": str(value)} for label, value in rows if not _is_blank(value)]


def _agent2_signal_rows(case_view: dict[str, Any]) -> list[dict[str, str]]:
    agent2_score = _dict_value(case_view.get("agent2_score"))
    evidence = _dict_value(agent2_score.get("evidence"))
    rows = []
    for flag in case_view.get("red_flags", []):
        rows.append(
            {
                "Senal": FLAG_LABELS.get(str(flag), str(flag)),
                "Dato usado": _agent2_flag_value(str(flag), evidence),
                "Lectura": FLAG_EXPLANATIONS.get(str(flag), "Senal para priorizar revision."),
            }
        )
    return rows


def _agent3_signal_rows(case_view: dict[str, Any]) -> list[dict[str, str]]:
    metrics = _dict_value(case_view.get("agent3_metrics"))
    metric_specs = [
        (
            "buyer_supplier_recurrence",
            "Contratos comprador-proveedor",
            "Numero de contratos que conectan al mismo comprador y adjudicatario.",
        ),
        (
            "buyer_supplier_contract_share",
            "Peso de la relacion",
            "Proporcion de contratos del comprador conectados con este adjudicatario.",
        ),
        (
            "supplier_contracts_count",
            "Contratos del adjudicatario",
            "Contratos del mismo adjudicatario dentro del lote analizado.",
        ),
        (
            "contract_betweenness_centrality",
            "Importancia del contrato en la red",
            "Indica si el contrato conecta varias partes de la red.",
        ),
        (
            "community_size",
            "Tamano de comunidad",
            "Entidades agrupadas alrededor del caso.",
        ),
        ("cpv_count", "Categorias CPV", "Numero de codigos CPV vinculados al contrato."),
    ]
    rows = []
    for key, label, reading in metric_specs:
        value = metrics.get(key)
        if _is_blank(value):
            continue
        formatted = _format_percent(value) if key == "buyer_supplier_contract_share" else (
            _format_metric(value)
        )
        rows.append({"Metrica": label, "Valor": formatted, "Lectura": reading})
    return rows


def _agent2_flag_value(flag: str, evidence: dict[str, Any]) -> str:
    if flag == "risky_procedure":
        return str(evidence.get("procedure") or "Procedimiento no informado")
    if flag == "awarded_above_estimate":
        estimated = _format_money(evidence.get("estimated_value_eur"))
        awarded = _format_money(evidence.get("awarded_value_eur"))
        return f"Estimado {estimated}; adjudicado {awarded}"
    return "Ver evidencia Agent2"


def _agent2_score_for_contract(payload: dict[str, Any], contract_key: str) -> dict[str, Any]:
    if _case_context_contract_key(payload) != contract_key:
        return {}
    score = _dict_value(payload.get("agent2_score"))
    if score:
        return score
    case_context = _dict_value(payload.get("case_context"))
    return _dict_value(case_context.get("agent2_score"))


def _ranking_score(
    score: dict[str, Any],
    recurrence: object,
    share: object,
    centrality: object,
    has_context: bool,
) -> float:
    value = 0.0
    if has_context:
        value += 2.0
    value += float(score.get("risk_score") or 0) * 3
    value += min(float(recurrence or 0), 5) * 0.25
    value += float(share or 0) * 0.5
    value += float(centrality or 0)
    return value


def _review_reason(
    red_flags: list[Any],
    recurrence: object,
    share: object,
    centrality: object,
) -> str:
    if red_flags:
        return _flag_list_label(red_flags)
    try:
        if float(recurrence or 0) >= 2:
            return "Relacion recurrente entre comprador y adjudicatario"
        if float(share or 0) >= 0.75:
            return "Alta concentracion comprador-adjudicatario"
        if float(centrality or 0) >= 0.25:
            return "Contrato relevante dentro de la red"
    except (TypeError, ValueError):
        pass
    return "Sin senales destacadas en esta muestra"


def _flag_list_label(flags: list[Any]) -> str:
    if not flags:
        return "Sin red flags Agent2"
    return "; ".join(FLAG_LABELS.get(str(flag), str(flag)) for flag in flags)


def _ensure_focus_contract(data, nodes: pd.DataFrame, edges: pd.DataFrame, selected_contract: str):
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


def _contract_option_label_from_table(contracts: pd.DataFrame, contract_key: str) -> str:
    matches = contracts[contracts["id_contrato"].astype(str) == contract_key]
    if matches.empty:
        return contract_key
    row = matches.iloc[0]
    return f"{contract_key} - {row['titulo']}"


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


def _row_for_contract(frame: pd.DataFrame, contract_key: str) -> dict[str, Any]:
    if frame.empty or "contract_key_canon" not in frame.columns:
        return {}
    matches = frame[frame["contract_key_canon"].astype(str) == str(contract_key)]
    if matches.empty:
        return {}
    return _clean_record(matches.iloc[0].to_dict())


def _concat_frames(first: pd.DataFrame, second: pd.DataFrame) -> pd.DataFrame:
    if second.empty:
        return first
    if first.empty:
        return second.copy()
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
        st.warning(f"No se pudo leer la ficha documental: {path}")
        return {}


def _render_missing_artifacts(output_dir: Path, missing: list[Path]) -> None:
    st.error("Faltan artefactos para construir la demo.")
    st.write(
        "La demo se puede regenerar desde codigo. Ejecuta el comando siguiente y vuelve a abrir "
        "el dashboard."
    )
    st.write(f"Carpeta revisada: `{output_dir}`")
    st.dataframe(
        [{"Artefacto requerido": str(path)} for path in missing],
        width="stretch",
        hide_index=True,
    )
    st.code(
        "$env:PYTHONPATH='scr'; python -m procurewatch.cli run-integrated-demo",
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


def _sorted_text_options(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if not _is_blank(value)})


def _community_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "comunidad" not in frame.columns:
        return []
    return sorted({str(value) for value in frame["comunidad"].tolist() if not _is_blank(value)})


def _node_type_label(value: object) -> str:
    return NODE_TYPE_LABELS.get(str(value), str(value))


def _edge_type_label(value: object) -> str:
    return EDGE_TYPE_LABELS.get(str(value), str(value))


def _risk_level_label(value: object) -> str:
    if _is_blank(value):
        return "No calculada"
    return RISK_LEVEL_LABELS.get(str(value), str(value))


def _document_type_label(value: object) -> str:
    if _is_blank(value):
        return "Documento"
    return DOCUMENT_TYPE_LABELS.get(str(value), str(value))


def _source_label(value: object) -> str:
    if _is_blank(value):
        return "No informada"
    return SOURCE_LABELS.get(str(value), str(value))


def _artifact_label(value: object) -> str:
    labels = {
        "nodes": "Nodos de red",
        "edges": "Relaciones",
        "contract_metrics": "Metricas por contrato",
        "entity_metrics": "Metricas por entidad",
        "communities": "Comunidades",
        "network_summary": "Resumen de red",
        "agent2_features": "Features para scoring/RAG",
        "agent2_features_schema": "Esquema de features",
        "report": "Reporte Agent3",
    }
    return labels.get(str(value), str(value))


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
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}"


def _format_score(value: object) -> str:
    if _is_blank(value):
        return "No disponible"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
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
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
            max-width: 1380px;
        }
        .pw-hero {
            align-items: center;
            background: #0f172a;
            border-radius: 8px;
            color: #f8fafc;
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.8rem;
            padding: 1.2rem 1.35rem;
        }
        .pw-hero h1 {
            color: #ffffff;
            font-size: 2rem;
            line-height: 1.1;
            margin: 0;
            padding: 0;
        }
        .pw-eyebrow {
            color: #93c5fd;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0;
            margin: 0 0 0.25rem;
            text-transform: uppercase;
        }
        .pw-hero-text {
            color: #dbeafe;
            font-size: 1rem;
            margin: 0.4rem 0 0;
            max-width: 760px;
        }
        .pw-hero-badge {
            background: #dcfce7;
            border: 1px solid #86efac;
            border-radius: 999px;
            color: #14532d;
            flex: 0 0 auto;
            font-size: 0.88rem;
            font-weight: 700;
            padding: 0.45rem 0.7rem;
        }
        .pw-callout,
        .pw-reading {
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-left: 5px solid #2563eb;
            border-radius: 8px;
            color: #1e293b;
            line-height: 1.45;
            margin: 0.6rem 0 1rem;
            padding: 0.8rem 0.95rem;
        }
        .pw-sidebar-note {
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 8px;
            color: #1e3a8a;
            font-size: 0.88rem;
            line-height: 1.35;
            margin: 0.6rem 0 0.8rem;
            padding: 0.7rem;
        }
        .pw-reading {
            border-left-color: #059669;
            background: #f0fdf4;
        }
        .pw-step {
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            padding: 0.8rem;
            min-height: 118px;
            background: #ffffff;
        }
        .pw-step-on {
            border-left: 5px solid #059669;
        }
        .pw-step-off {
            border-left: 5px solid #94a3b8;
            background: #f8fafc;
            color: #475569;
        }
        .pw-step-title {
            font-weight: 700;
            color: #0f172a;
        }
        .pw-step-state {
            font-size: 0.82rem;
            color: #334155;
            margin: 0.15rem 0 0.35rem;
        }
        .pw-step-text {
            font-size: 0.9rem;
            color: #334155;
            line-height: 1.35;
        }
        .pw-case-card {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            min-height: 178px;
            padding: 0.85rem;
        }
        .pw-case-card-selected {
            border-color: #2563eb;
            box-shadow: inset 0 0 0 2px rgba(37, 99, 235, 0.16);
        }
        .pw-card-kicker {
            color: #2563eb;
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
            text-transform: uppercase;
        }
        .pw-card-title {
            color: #0f172a;
            font-size: 1rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
        }
        .pw-card-subtitle {
            color: #475569;
            font-size: 0.9rem;
            line-height: 1.3;
            margin-bottom: 0.55rem;
        }
        .pw-card-line {
            color: #334155;
            font-size: 0.88rem;
            line-height: 1.35;
            margin-top: 0.3rem;
        }
        .pw-case-explainer {
            display: grid;
            gap: 0.75rem;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin: 0.8rem 0 1rem;
        }
        .pw-case-explainer > div,
        .pw-review-step,
        .pw-mini-card {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            color: #334155;
            padding: 0.8rem;
        }
        .pw-review-step {
            min-height: 122px;
        }
        .pw-review-step strong {
            color: #0f172a;
        }
        .pw-review-step p {
            margin: 0.4rem 0 0;
        }
        .pw-case-explainer strong {
            color: #0f172a;
            display: block;
            margin: 0.35rem 0 0.25rem;
        }
        .pw-case-explainer p {
            margin: 0;
        }
        .pw-badge {
            background: #e0f2fe;
            border: 1px solid #7dd3fc;
            border-radius: 999px;
            color: #075985;
            display: inline-block;
            font-size: 0.76rem;
            font-weight: 700;
            padding: 0.12rem 0.45rem;
        }
        .pw-mini-card {
            line-height: 1.7;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            padding: 0.75rem;
        }
        @media (max-width: 900px) {
            .pw-hero {
                align-items: flex-start;
                flex-direction: column;
            }
            .pw-case-explainer {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
