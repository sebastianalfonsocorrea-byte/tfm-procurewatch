from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from procurewatch.cli import doctor
from procurewatch.cli import main


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
        with mock.patch("procurewatch.agent2.run_agent2") as run_agent2_mock:
            run_agent2_mock.return_value = {
                "rows": 1,
                "activated_contract_rows": 1,
                "activated_flags": 1,
                "report_path": "agent2_run_report.json",
            }
            exit_code = main(["run-agent2-mvp"])

        self.assertEqual(exit_code, 0)
        run_agent2_mock.assert_called_once()
        kwargs = run_agent2_mock.call_args.kwargs
        self.assertEqual(kwargs["input_path"], Path("data/processed/agent2_contracts_canonical.parquet"))
        self.assertEqual(kwargs["output_dir"], Path("data/processed"))


if __name__ == "__main__":
    unittest.main()
