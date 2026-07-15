from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from procurewatch.agent3 import (
    GraphNode,
    GraphTables,
    build_agent2_feature_records,
    build_agent2_features_schema,
    build_demo_kpis,
    build_demo_subgraph,
    build_graph_tables,
    compute_contract_graph_metrics,
    compute_network_metrics,
    load_agent3_demo_data,
    load_graph_records_to_neo4j,
    run_agent3,
    select_explainable_cases,
    top_communities,
    top_entities,
    validate_canonical_columns,
)
from procurewatch.agent3.neo4j_store import prepare_edge_batches, prepare_node_batches
from procurewatch.cli import main
from procurewatch.dashboard_validation import validate_dashboard_demo
from procurewatch.integrated_demo import (
    DEMO_CONTRACT_KEY,
    DEMO_SOURCE_SNAPSHOT_ID,
    demo_contract_records,
    run_integrated_demo,
    write_demo_canonical,
)


class Agent3Tests(unittest.TestCase):
    def test_demo_contract_records_include_main_case_and_snapshot(self) -> None:
        records = demo_contract_records()
        by_contract = {str(item["contract_key_canon"]): item for item in records}

        self.assertEqual(len(records), 3)
        self.assertIn(DEMO_CONTRACT_KEY, by_contract)
        self.assertEqual(
            by_contract[DEMO_CONTRACT_KEY]["source_snapshot_id"],
            DEMO_SOURCE_SNAPSHOT_ID,
        )
        self.assertEqual(by_contract[DEMO_CONTRACT_KEY]["procedure"], "negociado sin publicidad")
        self.assertGreater(by_contract[DEMO_CONTRACT_KEY]["awarded_value_eur"], 100000.0)

    def test_write_demo_canonical_creates_parquet_with_required_fields(self) -> None:
        import pandas as pd

        temp_path = _test_workspace("integrated-demo-canonical")

        canonical_path = write_demo_canonical(temp_path)
        frame = pd.read_parquet(canonical_path)

        self.assertTrue(canonical_path.exists())
        self.assertEqual(len(frame), 3)
        self.assertIn("source_snapshot_id", frame.columns)
        self.assertIn(DEMO_CONTRACT_KEY, set(frame["contract_key_canon"].astype(str)))

    def test_run_integrated_demo_regenerates_agent2_agent3_agent4_artifacts(self) -> None:
        temp_path = _test_workspace("integrated-demo-flow")

        report = run_integrated_demo(output_dir=temp_path)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["contract_key_canon"], DEMO_CONTRACT_KEY)
        self.assertEqual(report["summary"]["canonical_rows"], 3)
        self.assertGreater(report["summary"]["agent3_nodes"], 0)
        self.assertGreater(report["summary"]["agent3_edges"], 0)
        self.assertGreater(report["summary"]["agent3_communities"], 0)
        self.assertEqual(report["summary"]["agent2_risk_score"], 0.5)
        self.assertIn("risky_procedure", report["summary"]["agent2_red_flags"])
        self.assertGreaterEqual(report["summary"]["agent4_evidences"], 1)
        self.assertGreaterEqual(report["summary"]["agent4_citations"], 1)
        self.assertTrue((temp_path / "agent2_contracts_canonical_demo.parquet").exists())
        self.assertTrue((temp_path / "agent3_graph_report.json").exists())
        self.assertTrue((temp_path / "agent4_case_context_integrated_demo.json").exists())
        self.assertTrue((temp_path / "agent2_agent3_agent4_demo_report.json").exists())
        self.assertTrue(all(item["passed"] for item in report["validations"]))
        self.assertIn("Demo sintetica y offline", " ".join(report["limitations"]))

    def test_validate_dashboard_demo_regenerates_and_renders_headless(self) -> None:
        temp_path = _test_workspace("dashboard-validation")

        report = validate_dashboard_demo(output_dir=temp_path)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["contract_key_canon"], DEMO_CONTRACT_KEY)
        self.assertEqual(report["kpis"]["contracts"], 3)
        self.assertGreater(report["kpis"]["nodes"], 0)
        self.assertGreater(report["kpis"]["edges"], 0)
        self.assertEqual(report["case_summary"]["risk_score"], 0.5)
        self.assertGreaterEqual(report["case_summary"]["evidences_count"], 1)
        self.assertGreaterEqual(report["case_summary"]["citations_count"], 1)
        self.assertTrue(report["streamlit_headless"]["executed"])
        self.assertEqual(report["streamlit_headless"]["exceptions"], [])
        self.assertGreaterEqual(report["streamlit_headless"]["tabs_count"], 8)
        self.assertIn("streamlit run frontend/agent3_demo.py", report["commands"]["open_dashboard"])
        self.assertIn("Resumen", report["capture_recommendations"])
        self.assertIn("Evolucion temporal", report["capture_recommendations"])
        self.assertEqual(report["temporal_summary"]["evaluated_contracts"], 3437)
        self.assertEqual(report["temporal_summary"]["dated_contracts"], 976)
        self.assertTrue((temp_path / "dashboard_validation_report.json").exists())
        self.assertTrue(all(item["passed"] for item in report["checks"]))

    def test_build_graph_tables_keeps_traceable_nodes_and_edges(self) -> None:
        graph = build_graph_tables(_contracts())

        node_ids = {node.node_id for node in graph.nodes}
        edge_types = {edge.edge_type for edge in graph.edges}

        self.assertIn("buyer:B1", node_ids)
        self.assertIn("supplier:S1", node_ids)
        self.assertIn("contract:C-001", node_ids)
        self.assertIn("cpv:71000000", node_ids)
        self.assertIn("source:BOE", node_ids)
        self.assertEqual(edge_types, {"PUBLISHED", "AWARDED_TO", "HAS_CPV", "FROM_SOURCE"})
        self.assertTrue(
            any(
                edge.contract_key_canon == "C-001"
                and edge.source == "boe"
                and edge.source_record_id == "BOE-1"
                for edge in graph.edges
            )
        )

    def test_build_graph_tables_is_deterministic_and_warns_missing_relations(self) -> None:
        graph_one = build_graph_tables(_contracts())
        graph_two = build_graph_tables(list(reversed(_contracts())))

        self.assertEqual(graph_one.node_records(), graph_two.node_records())
        self.assertEqual(graph_one.edge_records(), graph_two.edge_records())
        self.assertIn("Contracts without supplier relation: 1", graph_one.warnings)

    def test_compute_contract_graph_metrics_returns_contract_level_features(self) -> None:
        metrics = compute_contract_graph_metrics(_contracts())
        by_contract = {item.contract_key_canon: item for item in metrics}

        self.assertEqual(by_contract["C-001"].buyer_supplier_recurrence, 2)
        self.assertEqual(by_contract["C-001"].buyer_degree, 1)
        self.assertEqual(by_contract["C-001"].supplier_degree, 1)
        self.assertEqual(by_contract["C-001"].supplier_contracts_count, 2)
        self.assertEqual(by_contract["C-001"].buyer_supplier_contract_share, 1.0)
        self.assertNotIn("C-004", by_contract)

    def test_compute_network_metrics_returns_entity_communities_and_summary(self) -> None:
        graph = build_graph_tables(_contracts())

        result = compute_network_metrics(graph)
        by_node = {item["node_id"]: item for item in result.entity_records}

        self.assertEqual(len(result.entity_records), 10)
        self.assertEqual(by_node["contract:C-001"]["node_type"], "Contract")
        self.assertEqual(by_node["contract:C-001"]["component_size"], 10)
        self.assertGreater(by_node["buyer:B1"]["neighbor_count"], 0)
        self.assertIn("community_id", by_node["supplier:S1"])
        self.assertGreaterEqual(result.summary["community_count"], 1)
        self.assertEqual(result.summary["component_count"], 1)
        self.assertEqual(result.summary["largest_component_size"], 10)
        self.assertEqual(result.summary["betweenness_mode"], "exact")
        self.assertEqual(
            sum(item["contract_count"] for item in result.community_records),
            3,
        )

    def test_compute_network_metrics_exposes_reproducible_modularity_above_target(self) -> None:
        graph = build_graph_tables(_contracts())

        first = compute_network_metrics(graph)
        second = compute_network_metrics(graph)

        self.assertEqual(first.summary["modularity"], second.summary["modularity"])
        self.assertAlmostEqual(first.summary["modularity"], 0.3016528926, places=10)
        self.assertGreater(first.summary["modularity"], 0.30)

    def test_compute_network_metrics_has_no_modularity_without_edges(self) -> None:
        graph = GraphTables(
            nodes=[GraphNode(node_id="buyer:B1", node_type="Buyer", label="Buyer 1")],
            edges=[],
        )

        result = compute_network_metrics(graph)

        self.assertIsNone(result.summary["modularity"])

    def test_build_agent2_features_projects_graph_metrics_by_contract(self) -> None:
        graph = build_graph_tables(_contracts())
        contract_metrics = compute_contract_graph_metrics(_contracts())
        network_metrics = compute_network_metrics(graph)

        records = build_agent2_feature_records(
            graph_tables=graph,
            contract_metrics=contract_metrics,
            entity_metrics=network_metrics.entity_records,
            agent3_version="test",
            generated_at_utc="2026-06-22T00:00:00+00:00",
        )
        by_contract = {item["contract_key_canon"]: item for item in records}

        self.assertEqual(len(records), 3)
        self.assertEqual(by_contract["C-001"]["buyer_supplier_recurrence"], 2)
        self.assertEqual(by_contract["C-001"]["buyer_supplier_contract_share"], 1.0)
        self.assertTrue(by_contract["C-001"]["has_supplier"])
        self.assertEqual(by_contract["C-001"]["cpv_count"], 1)
        self.assertEqual(by_contract["C-004"]["buyer_supplier_recurrence"], 0)
        self.assertFalse(by_contract["C-004"]["has_supplier"])
        self.assertIsNone(by_contract["C-004"]["supplier_neighbor_count"])
        self.assertIn("community_id", by_contract["C-004"])

        schema = build_agent2_features_schema(
            agent3_version="test",
            generated_at_utc="2026-06-22T00:00:00+00:00",
        )
        self.assertEqual(schema["primary_key"], ["contract_key_canon"])
        self.assertIn("RF-03", schema["intended_red_flags"])
        self.assertIn("RF-04", schema["intended_red_flags"])

    def test_validate_canonical_columns_reports_missing_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "contract_key_canon"):
            validate_canonical_columns(["source", "buyer_name", "supplier_name", "cpv_codes_raw"])

    def test_run_agent3_writes_artifacts_and_report(self) -> None:
        import pandas as pd

        temp_path = _test_workspace("pipeline")
        input_path = temp_path / "canonical.parquet"
        output_dir = temp_path / "processed"
        output_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(_contracts()).to_parquet(input_path, index=False)

        report = run_agent3(input_path=input_path, output_dir=output_dir)

        self.assertEqual(report["input_rows"], 3)
        self.assertEqual(report["nodes_by_type"]["Contract"], 3)
        self.assertEqual(report["edges_by_type"]["AWARDED_TO"], 2)
        self.assertEqual(report["contracts_without_supplier"], 1)
        self.assertTrue((output_dir / "agent3_nodes.parquet").exists())
        self.assertTrue((output_dir / "agent3_edges.parquet").exists())
        self.assertTrue((output_dir / "agent3_contract_metrics.parquet").exists())
        self.assertTrue((output_dir / "agent3_entity_metrics.parquet").exists())
        self.assertTrue((output_dir / "agent3_communities.parquet").exists())
        self.assertTrue((output_dir / "agent3_network_summary.json").exists())
        self.assertTrue((output_dir / "agent3_agent2_features.parquet").exists())
        self.assertTrue((output_dir / "agent3_agent2_features_schema.json").exists())
        self.assertTrue((output_dir / "agent3_graph_report.json").exists())
        self.assertEqual(report["entity_metrics_rows"], 10)
        self.assertEqual(report["agent2_features_rows"], 3)
        self.assertGreaterEqual(report["community_count"], 1)
        self.assertGreater(report["modularity"], 0.30)
        schema = json.loads((output_dir / "agent3_agent2_features_schema.json").read_text())
        self.assertEqual(schema["dataset"], "agent3_agent2_features")

    def test_agent3_demo_helpers_load_outputs_and_select_cases(self) -> None:
        import pandas as pd

        temp_path = _test_workspace("demo")
        input_path = temp_path / "canonical.parquet"
        output_dir = temp_path / "processed"
        output_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(_contracts()).to_parquet(input_path, index=False)
        run_agent3(input_path=input_path, output_dir=output_dir)

        data = load_agent3_demo_data(output_dir)
        kpis = build_demo_kpis(data)
        cases = select_explainable_cases(data)
        nodes, edges = build_demo_subgraph(
            data,
            max_nodes=5,
            node_types={"Buyer", "Supplier", "Contract"},
        )

        self.assertEqual(kpis["contracts"], 3)
        self.assertEqual(kpis["agent2_features"], 3)
        self.assertEqual(len(cases), 3)
        self.assertEqual(len({item["contract_key_canon"] for item in cases}), 3)
        self.assertFalse(nodes.empty)
        self.assertTrue(set(nodes["node_type"]).issubset({"Buyer", "Supplier", "Contract"}))
        self.assertLessEqual(len(nodes), 5)
        self.assertIsNotNone(edges)
        self.assertFalse(top_communities(data).empty)
        self.assertFalse(top_entities(data, node_type="Buyer").empty)

    def test_cli_run_agent3_command(self) -> None:
        import pandas as pd

        temp_path = _test_workspace("cli")
        input_path = temp_path / "canonical.parquet"
        output_dir = temp_path / "processed"
        output_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(_contracts()).to_parquet(input_path, index=False)
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "run-agent3",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("Agente 3 ejecutado", output.getvalue())
        self.assertTrue((output_dir / "agent3_graph_report.json").exists())

    def test_prepare_neo4j_batches_groups_allowed_nodes_and_edges(self) -> None:
        graph = build_graph_tables(_contracts())

        node_batches = prepare_node_batches(graph.node_records())
        edge_batches = prepare_edge_batches(graph.edge_records())

        self.assertEqual(len(node_batches["Buyer"]), 1)
        self.assertEqual(len(node_batches["Contract"]), 3)
        self.assertEqual(len(edge_batches["PUBLISHED"]), 3)
        self.assertEqual(len(edge_batches["AWARDED_TO"]), 2)
        self.assertEqual(node_batches["Buyer"][0]["properties"]["node_type"], "Buyer")
        self.assertEqual(edge_batches["PUBLISHED"][0]["properties"]["edge_type"], "PUBLISHED")

    def test_prepare_neo4j_batches_rejects_unknown_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "Tipo de nodo Agent3 no permitido"):
            prepare_node_batches([{"node_id": "x:1", "node_type": "Unsafe", "label": "x"}])

        with self.assertRaisesRegex(ValueError, "Tipo de arista Agent3 no permitido"):
            prepare_edge_batches(
                [
                    {
                        "edge_id": "rel:1",
                        "source_node_id": "a",
                        "target_node_id": "b",
                        "edge_type": "DROP",
                    }
                ]
            )

    def test_load_graph_records_dispatches_neo4j_writes(self) -> None:
        graph = build_graph_tables(_contracts())
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__.return_value = session

        report = load_graph_records_to_neo4j(
            driver=driver,
            nodes=graph.node_records(),
            edges=graph.edge_records(),
            run_controls=False,
        )

        self.assertEqual(report["nodes_processed"], 10)
        self.assertEqual(report["edges_processed"], 11)
        self.assertEqual(report["nodes_by_type_input"]["Contract"], 3)
        write_names = [call.args[0].__name__ for call in session.execute_write.call_args_list]
        self.assertEqual(write_names[0], "_create_constraints")
        self.assertIn("_merge_nodes", write_names)
        self.assertIn("_merge_edges", write_names)

    def test_cli_agent3_load_neo4j_command(self) -> None:
        output = StringIO()
        expected_report = {
            "nodes_processed": 8,
            "edges_processed": 10,
            "controls": {
                "nodes_by_type": {"Contract": 3},
                "edges_by_type": {"PUBLISHED": 3},
            },
        }

        with patch(
            "procurewatch.agent3.neo4j_store.load_graph_to_neo4j",
            return_value=expected_report,
        ) as loader:
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "agent3-load-neo4j",
                        "--nodes",
                        "data/processed/agent3_nodes.parquet",
                        "--edges",
                        "data/processed/agent3_edges.parquet",
                        "--uri",
                        "bolt://neo4j-test:7687",
                        "--user",
                        "neo4j",
                        "--password",
                        "secret",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("Agente 3 cargado en Neo4j", output.getvalue())
        self.assertEqual(loader.call_args.kwargs["uri"], "bolt://neo4j-test:7687")
        self.assertEqual(loader.call_args.kwargs["user"], "neo4j")
        self.assertEqual(loader.call_args.kwargs["password"], "secret")


def _contracts() -> list[dict[str, object]]:
    return [
        {
            "contract_key_canon": "C-001",
            "source": "boe",
            "source_record_id": "BOE-1",
            "buyer_name": "Ayuntamiento Alfa",
            "buyer_id": "B1",
            "supplier_name": "Proveedor Uno",
            "supplier_id": "S1",
            "contract_title": "Servicios de ingenieria",
            "cpv_codes_raw": "71000000-8",
            "cpv_code_list": "71000000",
        },
        {
            "contract_key_canon": "C-002",
            "source": "place",
            "source_record_id": "PLACE-2",
            "buyer_name": "Ayuntamiento Alfa",
            "buyer_id": "B1",
            "supplier_name": "Proveedor Uno",
            "supplier_id": "S1",
            "contract_title": "Direccion de obra",
            "cpv_codes_raw": "71300000-1",
            "cpv_code_list": "71300000",
        },
        {
            "contract_key_canon": "C-004",
            "source": "opentender",
            "source_record_id": "OT-4",
            "buyer_name": "Ayuntamiento Alfa",
            "buyer_id": "B1",
            "supplier_name": "",
            "supplier_id": "",
            "contract_title": "Licitacion sin adjudicatario",
            "cpv_codes_raw": "71000000",
            "cpv_code_list": "",
        },
    ]


def _test_workspace(name: str) -> Path:
    path = Path("data/processed/agent3_test_artifacts") / name
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    unittest.main()
