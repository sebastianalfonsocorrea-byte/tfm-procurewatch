from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from procurewatch.agent2 import run_agent2


class Agent2Tests(unittest.TestCase):
    def test_mvp_generates_traceable_flags_and_scores(self) -> None:
        import pandas as pd

        contracts = pd.DataFrame(
            [
                {
                    "contract_key_canon": "contract-rf01-rf05",
                    "buyer_name": "Organismo B",
                    "supplier_name": "Proveedor C",
                    "source_tender_id": "t-1",
                    "procedure": "Abierto",
                    "publication_date": "2024-01-01",
                    "award_date": "2024-01-05",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 120.0,
                },
                {
                    "contract_key_canon": "contract-rf01-rf02",
                    "buyer_name": "Organismo A",
                    "supplier_name": "",
                    "source_tender_id": "t-2",
                    "procedure": "Menor",
                    "publication_date": "2024-02-10",
                    "award_date": "2024-02-12",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 90.0,
                },
                {
                    "contract_key_canon": "contract-rf02-rf03-rf04",
                    "buyer_name": "Organismo A",
                    "supplier_name": "Proveedor X",
                    "source_tender_id": "t-3",
                    "procedure": "Negociado sin publicidad",
                    "publication_date": "2024-03-01",
                    "award_date": "2024-03-04",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 95.0,
                },
                {
                    "contract_key_canon": "contract-rf02-rf03-rf04-b",
                    "buyer_name": "Organismo A",
                    "supplier_name": "Proveedor X",
                    "source_tender_id": "t-3",
                    "procedure": "Negociado sin publicidad",
                    "publication_date": "2024-03-02",
                    "award_date": "2024-03-05",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 95.0,
                },
                {
                    "contract_key_canon": "contract-rf02-rf06",
                    "buyer_name": "Organismo A",
                    "supplier_name": "Proveedor Y",
                    "source_tender_id": "t-4",
                    "procedure": "Menor",
                    "publication_date": "2024-04-10",
                    "award_date": "2024-04-09",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 95.0,
                },
            ]
        )

        with TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "canonical.parquet"
            contracts.to_parquet(input_path, index=False)

            report = run_agent2(input_path, root / "processed")
            flags = pd.read_parquet(report["outputs"]["risk_flags"])
            scores = pd.read_parquet(report["outputs"]["risk_scores"])
            supplier_summary = pd.read_parquet(report["outputs"]["supplier_risk_summary"])

            self.assertEqual(report["rows"], 5)
            self.assertEqual(report["evaluable_rows"], 5)
            self.assertEqual(report["not_evaluable_rows"], 0)
            self.assertEqual(report["activated_contract_rows"], 5)
            self.assertEqual(report["activated_flags"], 14)
            self.assertEqual(report["supplier_rows"], 3)
            self.assertEqual(
                set(report["flag_breakdown"].keys()),
                {"RF-01", "RF-02", "RF-03", "RF-04", "RF-05", "RF-06"},
            )
            self.assertIn("RF-05", flags["flag_code"].tolist())
            self.assertIn("RF-06", flags["flag_code"].tolist())

            rf05_row = scores.set_index("contract_key_canon").loc["contract-rf01-rf05"]
            self.assertEqual(rf05_row["risk_score"], 40.0)
            self.assertEqual(rf05_row["risk_level"], "medio")
            self.assertCountEqual(json.loads(rf05_row["top_flags"]), ["RF-01", "RF-05"])

            rf01_row = scores.set_index("contract_key_canon").loc["contract-rf01-rf02"]
            self.assertEqual(rf01_row["risk_score"], 50.0)
            self.assertEqual(rf01_row["risk_level"], "alto")
            self.assertCountEqual(json.loads(rf01_row["top_flags"]), ["RF-01", "RF-02", "RF-06"])

            recurrent_row = scores.set_index("contract_key_canon").loc["contract-rf02-rf03-rf04"]
            self.assertEqual(recurrent_row["risk_score"], 60.0)
            self.assertEqual(recurrent_row["risk_level"], "alto")
            self.assertCountEqual(json.loads(recurrent_row["top_flags"]), ["RF-02", "RF-03", "RF-04"])

            temporal_row = scores.set_index("contract_key_canon").loc["contract-rf02-rf06"]
            self.assertEqual(temporal_row["risk_score"], 50.0)
            self.assertEqual(temporal_row["risk_level"], "alto")
            self.assertCountEqual(json.loads(temporal_row["top_flags"]), ["RF-01", "RF-02", "RF-06"])

            self.assertTrue((scores["evaluation_status"] == "evaluado").all())
            self.assertEqual(len(supplier_summary), 3)
            self.assertIn("score_riesgo_agregado", supplier_summary.columns)
            self.assertIn("red_flags_recurrentes", supplier_summary.columns)
            self.assertIn("source_snapshot_id", report)
            self.assertTrue((root / "processed" / "agent2_run_report.json").exists())

    def test_rf05_threshold_is_configurable(self) -> None:
        import pandas as pd

        with TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "canonical.parquet"
            pd.DataFrame(
                [
                    {
                        "contract_key_canon": "contract-1",
                        "buyer_name": "Organismo",
                        "supplier_name": "Proveedor",
                        "source_tender_id": "t-x",
                        "procedure": "Abierto",
                        "publication_date": "2024-01-01",
                        "award_date": "2024-01-03",
                        "estimated_value_eur": 100.0,
                        "awarded_value_eur": 115.0,
                    }
                ]
            ).to_parquet(input_path, index=False)

            report = run_agent2(input_path, root / "processed", deviation_threshold=0.20)

            self.assertEqual(report["evaluable_rows"], 1)
            self.assertEqual(report["flag_breakdown"].get("RF-05", 0), 0)
            scores = pd.read_parquet(report["outputs"]["risk_scores"])
            self.assertEqual(scores.loc[0, "risk_score"], 30.0)
            self.assertEqual(scores.loc[0, "risk_level"], "medio")
            self.assertCountEqual(json.loads(scores.loc[0, "top_flags"]), ["RF-01", "RF-06"])
            self.assertEqual(report["supplier_rows"], 1)


if __name__ == "__main__":
    unittest.main()
