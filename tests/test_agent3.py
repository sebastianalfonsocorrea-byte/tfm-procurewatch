from __future__ import annotations

import unittest

from procurewatch.agent3 import (
    build_graph_tables,
    compute_contract_graph_metrics,
    validate_canonical_columns,
)


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


if __name__ == "__main__":
    unittest.main()
