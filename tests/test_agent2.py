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
                    "contract_key_canon": "contract-rf05",
                    "buyer_name": "Organismo B",
                    "supplier_name": "Proveedor C",
                    "procedure": "Abierto",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 120.0,
                },
                {
                    "contract_key_canon": "contract-rf01-rf02",
                    "buyer_name": "Organismo A",
                    "supplier_name": "",
                    "procedure": "Menor",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 90.0,
                },
                {
                    "contract_key_canon": "contract-rf02-rf03-rf04",
                    "buyer_name": "Organismo A",
                    "supplier_name": "Proveedor X",
                    "procedure": "Negociado sin publicidad",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 95.0,
                },
                {
                    "contract_key_canon": "contract-rf03-rf04",
                    "buyer_name": "Organismo A",
                    "supplier_name": "Proveedor X",
                    "procedure": "Abierto",
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

            self.assertEqual(report["rows"], 4)
            self.assertEqual(report["evaluable_rows"], 4)
            self.assertEqual(report["not_evaluable_rows"], 0)
            self.assertEqual(report["activated_contract_rows"], 4)
            self.assertEqual(report["activated_flags"], 8)
            self.assertEqual(set(report["flag_breakdown"].keys()), {"RF-01", "RF-02", "RF-03", "RF-04", "RF-05"})
            self.assertEqual(flags["flag_code"].nunique(), 5)
            self.assertIn("RF-05", flags["flag_code"].tolist())

            rf05_row = scores.set_index("contract_key_canon").loc["contract-rf05"]
            self.assertEqual(rf05_row["risk_score"], 25.0)
            self.assertEqual(rf05_row["risk_level"], "medio")
            self.assertEqual(json.loads(rf05_row["top_flags"]), ["RF-05"])

            rf01_row = scores.set_index("contract_key_canon").loc["contract-rf01-rf02"]
            self.assertEqual(rf01_row["risk_score"], 35.0)
            self.assertEqual(rf01_row["risk_level"], "medio")
            self.assertCountEqual(json.loads(rf01_row["top_flags"]), ["RF-01", "RF-02"])

            recurrent_row = scores.set_index("contract_key_canon").loc["contract-rf02-rf03-rf04"]
            self.assertEqual(recurrent_row["risk_score"], 60.0)
            self.assertEqual(recurrent_row["risk_level"], "alto")
            self.assertCountEqual(json.loads(recurrent_row["top_flags"]), ["RF-02", "RF-03", "RF-04"])

            self.assertTrue((scores["evaluation_status"] == "evaluado").all())
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
                        "procedure": "Abierto",
                        "estimated_value_eur": 100.0,
                        "awarded_value_eur": 115.0,
                    }
                ]
            ).to_parquet(input_path, index=False)

            report = run_agent2(input_path, root / "processed", deviation_threshold=0.20)

            self.assertEqual(report["evaluable_rows"], 1)
            self.assertEqual(report["flag_breakdown"].get("RF-05", 0), 0)
            scores = pd.read_parquet(report["outputs"]["risk_scores"])
            self.assertEqual(scores.loc[0, "risk_score"], 0.0)
            self.assertEqual(scores.loc[0, "risk_level"], "bajo")


if __name__ == "__main__":
    unittest.main()
