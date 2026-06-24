from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from procurewatch.cli import doctor, main


class CliTests(unittest.TestCase):
    def test_doctor_reports_scaffold_status(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = doctor()

        self.assertEqual(exit_code, 0)
        self.assertIn("ProcureWatch Analytics", output.getvalue())
        self.assertIn("Python", output.getvalue())

    def test_run_mvp_uses_env_postgres_dsn(self) -> None:
        with mock.patch("procurewatch.cli.Settings.from_env") as from_env:
            from_env.return_value = mock.Mock(postgres_dsn="postgresql://demo")
            with mock.patch("procurewatch.agent1.run_agent1") as run_agent1_mock:
                exit_code = main(["run-mvp", "--year", "2024", "--cpv-prefix", "71"])

        self.assertEqual(exit_code, 0)
        run_agent1_mock.assert_called_once()
        kwargs = run_agent1_mock.call_args.kwargs
        self.assertEqual(kwargs["postgres_dsn"], "postgresql://demo")
        self.assertTrue(kwargs["write_postgres"])
        self.assertEqual(kwargs["output_dir"], Path("data/processed"))

    def test_run_agent2_mvp_uses_default_canonical(self) -> None:
        with mock.patch("procurewatch.agent2.run_agent2_mvp") as run_agent2_mvp_mock:
            run_agent2_mvp_mock.return_value = {
                "rows": 1,
                "activated_contract_rows": 1,
                "activated_flags": 1,
                "report_path": "agent2_run_report.json",
            }
            exit_code = main(["run-agent2-mvp"])

        self.assertEqual(exit_code, 0)
        run_agent2_mvp_mock.assert_called_once()
        kwargs = run_agent2_mvp_mock.call_args.kwargs
        self.assertEqual(
            kwargs["input_path"],
            Path("data/processed/agent2_contracts_canonical.parquet"),
        )
        self.assertEqual(kwargs["output_dir"], Path("data/processed"))
        self.assertEqual(
            kwargs["agent3_features_path"],
            Path("data/processed/agent3_agent2_features.parquet"),
        )

    def test_run_integrated_demo_command_uses_defaults_and_prints_report(self) -> None:
        report = {
            "status": "ready",
            "contract_key_canon": "PW-2024-0001",
            "artifacts": {
                "canonical": "data/processed/demo/agent2_contracts_canonical_demo.parquet",
                "integrated_report": (
                    "data/processed/demo/agent2_agent3_agent4_demo_report.json"
                ),
            },
            "summary": {
                "agent3_nodes": 11,
                "agent3_edges": 13,
                "agent2_risk_score": 0.5,
                "agent2_red_flags": ["risky_procedure", "awarded_above_estimate"],
                "agent4_evidences": 2,
                "agent4_citations": 2,
            },
        }
        with mock.patch("procurewatch.integrated_demo.run_integrated_demo") as run_demo_mock:
            run_demo_mock.return_value = report
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["run-integrated-demo"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Demo integrada Agent2-Agent3-Agent4 [ready]", output.getvalue())
        run_demo_mock.assert_called_once()
        kwargs = run_demo_mock.call_args.kwargs
        self.assertEqual(
            kwargs["output_dir"],
            Path("data/processed/agent3_agent4_demo_2026_06_23"),
        )
        self.assertEqual(kwargs["contract_key_canon"], "PW-2024-0001")
        self.assertEqual(
            kwargs["corpus_index"],
            Path("data/synthetic/agent4_corpus/agent4_corpus_index.json"),
        )

    def test_run_batch_passes_paths_and_prints_manifest(self) -> None:
        with mock.patch("procurewatch.batch.run_batch") as run_batch_mock:
            run_batch_mock.return_value = {
                "status": "executed",
                "batch_id": "weekly_test",
                "agent1_executed": True,
                "changed_sources": ["boe_raw"],
                "missing_required_inputs": [],
                "batch_manifest_path": "data/manifest/batches/weekly/weekly_test/manifest.json",
            }
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "run-batch",
                        "--run-mode",
                        "weekly",
                        "--processed-dir",
                        "tmp/processed",
                        "--manifest-path",
                        "tmp/place_sources.json",
                        "--batch-state-path",
                        "tmp/state.json",
                        "--batch-manifest-dir",
                        "tmp/manifests",
                        "--datos-gob-dir",
                        "tmp/datos_gob",
                        "--raw-dir",
                        "tmp/raw",
                        "--cleanup-downloads",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("run-batch [executed]", output.getvalue())
        self.assertIn("manifest:", output.getvalue())
        run_batch_mock.assert_called_once()
        kwargs = run_batch_mock.call_args.kwargs
        self.assertEqual(kwargs["processed_dir"], Path("tmp/processed"))
        self.assertEqual(kwargs["manifest_path"], Path("tmp/place_sources.json"))
        self.assertEqual(kwargs["batch_state_path"], Path("tmp/state.json"))
        self.assertEqual(kwargs["batch_manifest_dir"], Path("tmp/manifests"))
        self.assertEqual(kwargs["datos_gob_dir"], Path("tmp/datos_gob"))
        self.assertEqual(kwargs["raw_dir"], Path("tmp/raw"))
        self.assertTrue(kwargs["cleanup_downloads"])


if __name__ == "__main__":
    unittest.main()
