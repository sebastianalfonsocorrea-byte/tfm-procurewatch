from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from procurewatch.agent2 import run_agent2


class Agent2Tests(unittest.TestCase):
    def test_rf05_generates_traceable_flags_and_preserves_non_evaluable_rows(self) -> None:
        import pandas as pd

        contracts = pd.DataFrame(
            [
                {
                    "contract_key_canon": "contract-ok",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 105.0,
                },
                {
                    "contract_key_canon": "contract-flagged",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 120.0,
                },
                {
                    "contract_key_canon": "contract-not-evaluable",
                    "estimated_value_eur": None,
                    "awarded_value_eur": 90.0,
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

            self.assertEqual(report["evaluable_rows"], 2)
            self.assertEqual(report["activated_flags"], 1)
            self.assertEqual(flags.loc[0, "flag_code"], "RF-05")
            self.assertIn("20.00%", flags.loc[0, "evidence_text"])
            self.assertEqual(json.loads(flags.loc[0, "evidence_fields"])[0], "estimated_value_eur")

            flagged = scores.set_index("contract_key_canon").loc["contract-flagged"]
            self.assertEqual(flagged["risk_score"], 25.0)
            self.assertEqual(flagged["risk_level"], "medio")
            self.assertEqual(flagged["evaluation_status"], "evaluado")

            missing = scores.set_index("contract_key_canon").loc["contract-not-evaluable"]
            self.assertTrue(pd.isna(missing["risk_score"]))
            self.assertEqual(missing["evaluation_status"], "no_evaluable")

    def test_rf05_threshold_is_configurable(self) -> None:
        import pandas as pd

        with TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "canonical.parquet"
            pd.DataFrame(
                [
                    {
                        "contract_key_canon": "contract-1",
                        "estimated_value_eur": 100.0,
                        "awarded_value_eur": 115.0,
                    }
                ]
            ).to_parquet(input_path, index=False)

            report = run_agent2(input_path, root / "processed", deviation_threshold=0.20)

            self.assertEqual(report["evaluable_rows"], 1)
            self.assertEqual(report["activated_flags"], 0)


if __name__ == "__main__":
    unittest.main()
