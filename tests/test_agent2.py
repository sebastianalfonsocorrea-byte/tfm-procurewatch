from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from uuid import uuid4

from procurewatch.agent2 import Agent2Contract, run_agent2, score_contract
from procurewatch.cli import main


class Agent2Tests(unittest.TestCase):
    def test_score_contract_keeps_compatible_red_flags_and_risk_level(self) -> None:
        contract = Agent2Contract(
            contract_key_canon="C-001",
            source="boe",
            supplier_name="",
            estimated_value_eur=100.0,
            awarded_value_eur=125.0,
            procedure="abierto",
        )

        score = score_contract(contract)

        self.assertEqual(score.red_flags, ["missing_supplier", "awarded_above_estimate"])
        self.assertEqual(score.risk_score, 0.5)
        self.assertEqual(score.risk_level, "medium")
        self.assertEqual(score.flags_count, 2)
        self.assertEqual(score.top_flags, ["missing_supplier", "awarded_above_estimate"])

    def test_score_contract_detects_risky_procedure(self) -> None:
        contract = Agent2Contract(
            contract_key_canon="C-002",
            source="place",
            supplier_name="Proveedor Uno",
            procedure="Procedimiento negociado sin publicidad",
        )

        score = score_contract(contract)

        self.assertEqual(score.red_flags, ["risky_procedure"])
        self.assertEqual(score.risk_score, 0.25)
        self.assertEqual(score.risk_level, "low")
        self.assertEqual(score.evidence["procedure"], "Procedimiento negociado sin publicidad")

    def test_run_agent2_writes_scores_flags_and_report(self) -> None:
        import pandas as pd

        workspace = _test_workspace("pipeline")
        input_path = workspace / "canonical.parquet"
        output_dir = workspace / "processed"
        output_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(_contracts()).to_parquet(input_path, index=False)

        report = run_agent2(
            input_path=input_path,
            output_dir=output_dir,
            source_snapshot_id="snapshot-test",
        )
        scores = pd.read_parquet(output_dir / "agent2_risk_scores.parquet")
        flags = pd.read_parquet(output_dir / "agent2_risk_flags.parquet")
        report_payload = json.loads((output_dir / "agent2_scoring_report.json").read_text())

        self.assertEqual(report["input_rows"], 3)
        self.assertEqual(report["scores_rows"], 3)
        self.assertEqual(report["flags_rows"], 3)
        self.assertTrue((output_dir / "agent2_risk_scores_schema.json").exists())
        self.assertTrue((output_dir / "agent2_risk_flags_schema.json").exists())
        self.assertEqual(set(scores["risk_level"].tolist()), {"medium", "low", "none"})
        self.assertEqual(set(flags["flag_code"].tolist()), {"DQ-01", "RF-02", "RF-05"})
        self.assertEqual(report_payload["source_snapshot_id"], "snapshot-test")
        self.assertEqual(report_payload["flag_code_counts"]["RF-05"], 1)

    def test_cli_run_agent2_command(self) -> None:
        import pandas as pd

        workspace = _test_workspace("cli")
        input_path = workspace / "canonical.parquet"
        output_dir = workspace / "processed"
        output_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(_contracts()).to_parquet(input_path, index=False)
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "run-agent2",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("Agente 2 ejecutado", output.getvalue())
        self.assertTrue((output_dir / "agent2_scoring_report.json").exists())


def _contracts() -> list[dict[str, object]]:
    return [
        {
            "contract_key_canon": "C-001",
            "source": "boe",
            "source_record_id": "BOE-1",
            "supplier_name": "",
            "procedure": "abierto",
            "estimated_value_eur": 100.0,
            "awarded_value_eur": 125.0,
        },
        {
            "contract_key_canon": "C-002",
            "source": "place",
            "source_record_id": "PLACE-2",
            "supplier_name": "Proveedor Uno",
            "procedure": "Procedimiento negociado sin publicidad",
            "estimated_value_eur": 200.0,
            "awarded_value_eur": 180.0,
        },
        {
            "contract_key_canon": "C-003",
            "source": "opentender",
            "source_record_id": "OT-3",
            "supplier_name": "Proveedor Dos",
            "procedure": "abierto",
            "estimated_value_eur": 300.0,
            "awarded_value_eur": 250.0,
        },
    ]


def _test_workspace(name: str) -> Path:
    path = Path("data/processed/agent2_test_artifacts") / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    unittest.main()
