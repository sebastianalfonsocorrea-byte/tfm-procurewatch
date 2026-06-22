from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from procurewatch.agent3 import (
    build_graph_tables,
    compute_contract_graph_metrics,
    run_agent3,
    validate_canonical_columns,
)
from procurewatch.cli import main


class Agent3Tests(unittest.TestCase):
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
        self.assertTrue((output_dir / "agent3_graph_report.json").exists())

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
