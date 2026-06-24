from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from uuid import uuid4

from procurewatch.agent2 import Agent2Contract, run_agent2, run_agent2_mvp, score_contract
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

    def test_run_agent2_mvp_generates_traceable_flags_and_scores(self) -> None:
        import pandas as pd

        workspace = _test_workspace("mvp")
        input_path = workspace / "canonical.parquet"
        output_dir = workspace / "processed"
        pd.DataFrame(_mvp_contracts()).to_parquet(input_path, index=False)

        report = run_agent2_mvp(input_path=input_path, output_dir=output_dir)
        flags = pd.read_parquet(report["outputs"]["risk_flags"])
        scores = pd.read_parquet(report["outputs"]["risk_scores"])
        scores_by_contract = scores.set_index("contract_key_canon")

        self.assertEqual(report["rows"], 5)
        self.assertEqual(report["evaluable_rows"], 5)
        self.assertEqual(report["not_evaluable_rows"], 0)
        self.assertEqual(report["activated_contract_rows"], 5)
        self.assertEqual(report["activated_flags"], 14)
        self.assertEqual(
            set(report["flag_breakdown"].keys()),
            {"RF-01", "RF-02", "RF-03", "RF-04", "RF-05", "RF-06"},
        )
        self.assertIn("RF-05", flags["flag_code"].tolist())
        self.assertIn("RF-06", flags["flag_code"].tolist())

        rf05_row = scores_by_contract.loc["contract-rf01-rf05"]
        self.assertEqual(rf05_row["risk_score"], 40.0)
        self.assertEqual(rf05_row["risk_level"], "medio")
        self.assertCountEqual(json.loads(rf05_row["top_flags"]), ["RF-01", "RF-05"])

        rf01_row = scores_by_contract.loc["contract-rf01-rf02"]
        self.assertEqual(rf01_row["risk_score"], 50.0)
        self.assertEqual(rf01_row["risk_level"], "alto")
        self.assertCountEqual(json.loads(rf01_row["top_flags"]), ["RF-01", "RF-02", "RF-06"])

        recurrent_row = scores_by_contract.loc["contract-rf02-rf03-rf04"]
        self.assertEqual(recurrent_row["risk_score"], 60.0)
        self.assertEqual(recurrent_row["risk_level"], "alto")
        self.assertCountEqual(
            json.loads(recurrent_row["top_flags"]),
            ["RF-02", "RF-03", "RF-04"],
        )

        temporal_row = scores_by_contract.loc["contract-rf02-rf06"]
        self.assertEqual(temporal_row["risk_score"], 50.0)
        self.assertEqual(temporal_row["risk_level"], "alto")
        self.assertCountEqual(
            json.loads(temporal_row["top_flags"]),
            ["RF-01", "RF-02", "RF-06"],
        )

        self.assertTrue((scores["evaluation_status"] == "evaluado").all())
        self.assertFalse(scores["agent3_features_used"].any())
        self.assertEqual(report["agent3_features_status"], "ignored")
        self.assertIn("source_snapshot_id", report)
        self.assertTrue((output_dir / "agent2_run_report.json").exists())

    def test_run_agent2_mvp_rf05_threshold_is_configurable(self) -> None:
        import pandas as pd

        workspace = _test_workspace("mvp-threshold")
        input_path = workspace / "canonical.parquet"
        output_dir = workspace / "processed"
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

        report = run_agent2_mvp(
            input_path=input_path,
            output_dir=output_dir,
            deviation_threshold=0.20,
        )

        self.assertEqual(report["evaluable_rows"], 1)
        self.assertEqual(report["flag_breakdown"].get("RF-05", 0), 0)
        scores = pd.read_parquet(report["outputs"]["risk_scores"])
        self.assertEqual(scores.loc[0, "risk_score"], 30.0)
        self.assertEqual(scores.loc[0, "risk_level"], "medio")
        self.assertCountEqual(json.loads(scores.loc[0, "top_flags"]), ["RF-01", "RF-06"])

    def test_run_agent2_mvp_uses_agent3_features_for_rf03_rf04(self) -> None:
        import pandas as pd

        workspace = _test_workspace("mvp-agent3-features")
        input_path = workspace / "canonical.parquet"
        features_path = workspace / "agent3_agent2_features.parquet"
        output_dir = workspace / "processed"
        pd.DataFrame(_mvp_agent3_feature_contracts()).to_parquet(input_path, index=False)
        pd.DataFrame(
            [
                {
                    "contract_key_canon": "contract-agent3-target",
                    "buyer_supplier_recurrence": 3,
                    "buyer_supplier_contract_share": 0.75,
                    "agent3_version": "test-agent3",
                }
            ]
        ).to_parquet(features_path, index=False)

        report = run_agent2_mvp(
            input_path=input_path,
            output_dir=output_dir,
            agent3_features_path=features_path,
        )

        flags = pd.read_parquet(report["outputs"]["risk_flags"])
        scores = pd.read_parquet(report["outputs"]["risk_scores"]).set_index("contract_key_canon")
        target_score = scores.loc["contract-agent3-target"]
        target_flags = flags[flags["contract_key_canon"].eq("contract-agent3-target")]

        self.assertEqual(report["agent3_features_status"], "used")
        self.assertEqual(report["agent3_features_rows"], 1)
        self.assertEqual(report["agent3_features_matched_rows"], 1)
        self.assertEqual(report["flag_breakdown"], {"RF-03": 1, "RF-04": 1})
        self.assertTrue(bool(target_score["agent3_features_used"]))
        self.assertEqual(target_score["risk_score"], 40.0)
        self.assertEqual(target_score["risk_level"], "medio")
        self.assertCountEqual(json.loads(target_score["top_flags"]), ["RF-03", "RF-04"])
        self.assertCountEqual(target_flags["flag_code"].tolist(), ["RF-03", "RF-04"])
        self.assertTrue(target_flags["evidence_text"].str.contains("Agent3").all())
        self.assertTrue(target_flags["evidence_fields"].str.contains("agent3").all())

    def test_run_agent2_mvp_tolerates_missing_agent3_features_path(self) -> None:
        import pandas as pd

        workspace = _test_workspace("mvp-agent3-missing")
        input_path = workspace / "canonical.parquet"
        output_dir = workspace / "processed"
        pd.DataFrame(_mvp_agent3_feature_contracts()).to_parquet(input_path, index=False)

        report = run_agent2_mvp(
            input_path=input_path,
            output_dir=output_dir,
            agent3_features_path=workspace / "missing_agent3_features.parquet",
        )

        scores = pd.read_parquet(report["outputs"]["risk_scores"])
        flags = pd.read_parquet(report["outputs"]["risk_flags"])

        self.assertEqual(report["agent3_features_status"], "missing")
        self.assertEqual(report["agent3_features_rows"], 0)
        self.assertEqual(report["agent3_features_matched_rows"], 0)
        self.assertTrue(report["agent3_features_warnings"])
        self.assertEqual(report["activated_flags"], 0)
        self.assertTrue(flags.empty)
        self.assertFalse(scores["agent3_features_used"].any())


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


def _mvp_contracts() -> list[dict[str, object]]:
    return [
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


def _mvp_agent3_feature_contracts() -> list[dict[str, object]]:
    return [
        {
            "contract_key_canon": "contract-agent3-target",
            "buyer_name": "Organismo Agent3",
            "supplier_name": "Proveedor Concentrado",
            "source_tender_id": "t-agent3",
            "procedure": "Abierto",
            "publication_date": "2024-05-01",
            "award_date": "2024-05-10",
            "estimated_value_eur": 100.0,
            "awarded_value_eur": 95.0,
        },
        {
            "contract_key_canon": "contract-agent3-filler",
            "buyer_name": "Organismo Agent3",
            "supplier_name": "Proveedor Alternativo",
            "source_tender_id": "t-agent3",
            "procedure": "Abierto",
            "publication_date": "2024-05-02",
            "award_date": "2024-05-12",
            "estimated_value_eur": 100.0,
            "awarded_value_eur": 95.0,
        },
    ]


def _test_workspace(name: str) -> Path:
    path = Path("data/processed/agent2_test_artifacts") / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    unittest.main()
