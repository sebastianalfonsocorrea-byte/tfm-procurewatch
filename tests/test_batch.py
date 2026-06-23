from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import importlib.util
import unittest
from unittest import mock

from procurewatch.batch import run_batch


class BatchTests(unittest.TestCase):
    @unittest.skipIf(
        importlib.util.find_spec("requests") is None,
        "requests no disponible en entorno de test actual",
    )
    def test_weekly_batch_skips_when_no_source_changes(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            raw_dir = workspace / "data/raw"
            processed_dir = workspace / "data/processed"
            raw_dir.mkdir(parents=True)
            processed_dir.mkdir(parents=True)

            boe_input = raw_dir / "boe.csv"
            open_tender_input = raw_dir / "opentender.zip"
            boe_input.write_text("header\n")
            open_tender_input.write_text("zip-content")

            place_dir = raw_dir / "place" / "profiles"
            place_dir.mkdir(parents=True)
            place_path = place_dir / "profile_2024.zip"
            place_path.write_bytes(b"place")

            manifest_path = workspace / "place_sources.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "generated_for": "ProcureWatch-Test",
                        "source_family": "test",
                        "datasets": [
                            {
                                "id": "place_profiles",
                                "name": "Perfiles test",
                                "first_year": 2024,
                                "annual_url_pattern": "profile_{year}.zip",
                                "raw_subdir": "place/profiles",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            batch_state_path = processed_dir / "run_batch_state.json"
            hash_file = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            batch_state_path.write_text(
                json.dumps(
                    {
                        "source_snapshots": [
                            {
                                "source_id": "boe_raw",
                                "exists": True,
                                "size_bytes": boe_input.stat().st_size,
                                "sha256": hash_file(boe_input),
                                "modified_utc": None,
                                "path": str(boe_input),
                            },
                            {
                                "source_id": "opentender_raw",
                                "exists": True,
                                "size_bytes": open_tender_input.stat().st_size,
                                "sha256": hash_file(open_tender_input),
                                "modified_utc": None,
                                "path": str(open_tender_input),
                            },
                            {
                                "source_id": "place::place_profiles",
                                "exists": True,
                                "size_bytes": place_path.stat().st_size,
                                "sha256": hash_file(place_path),
                                "modified_utc": None,
                                "path": str(place_path),
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("procurewatch.batch.run_agent1") as run_agent1_mock:
                with mock.patch("procurewatch.batch.run_agent2") as run_agent2_mock:
                    result = run_batch(
                        run_mode="weekly",
                        year=2024,
                        cpv_prefix="71",
                        force=False,
                        place_download=False,
                        place_datasets=["place_profiles"],
                        include_datos_gob=False,
                        boe_input=boe_input,
                        open_tender_input=open_tender_input,
                        raw_dir=raw_dir,
                        processed_dir=processed_dir,
                        manifest_path=manifest_path,
                        batch_state_path=batch_state_path,
                        batch_manifest_dir=workspace / "data/manifest/batches",
                    )

            self.assertFalse(run_agent1_mock.called)
            self.assertFalse(run_agent2_mock.called)
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["agent1_executed"], False)
            self.assertEqual(result["agent2_executed"], False)

    @unittest.skipIf(
        importlib.util.find_spec("requests") is None,
        "requests no disponible en entorno de test actual",
    )
    def test_weekly_batch_runs_agent2_when_canonical_changes(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            raw_dir = workspace / "data/raw"
            processed_dir = workspace / "data/processed"
            raw_dir.mkdir(parents=True)
            processed_dir.mkdir(parents=True)

            boe_input = raw_dir / "boe.csv"
            open_tender_input = raw_dir / "opentender.zip"
            boe_input.write_text("header\nchanged\n")
            open_tender_input.write_text("zip-content")

            place_dir = raw_dir / "place" / "profiles"
            place_dir.mkdir(parents=True)
            place_path = place_dir / "profile_2024.zip"
            place_path.write_bytes(b"place")

            manifest_path = workspace / "place_sources.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "generated_for": "ProcureWatch-Test",
                        "source_family": "test",
                        "datasets": [
                            {
                                "id": "place_profiles",
                                "name": "Perfiles test",
                                "first_year": 2024,
                                "annual_url_pattern": "profile_{year}.zip",
                                "raw_subdir": "place/profiles",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            canonical_path = processed_dir / "agent2_contracts_canonical.parquet"
            canonical_path.write_text("contract_key_canon\ncanon-1\n", encoding="utf-8")
            agent1_report_path = processed_dir / "agent1_run_report.json"
            agent1_report_path.write_text("{}", encoding="utf-8")
            agent2_report_path = processed_dir / "agent2_run_report.json"
            agent2_report_path.write_text("{}", encoding="utf-8")
            for path in [
                processed_dir / "agent2_risk_flags.parquet",
                processed_dir / "agent2_risk_scores.parquet",
                processed_dir / "agent2_supplier_risk_summary.parquet",
                processed_dir / "agent2_model_comparison.parquet",
            ]:
                path.write_text("ok", encoding="utf-8")

            with mock.patch("procurewatch.batch.run_agent1") as run_agent1_mock:
                run_agent1_mock.return_value = {
                    "agent1_run_report_path": str(agent1_report_path),
                    "canonical_agent2": {"path": str(canonical_path)},
                }
                with mock.patch("procurewatch.batch.run_agent2") as run_agent2_mock:
                    run_agent2_mock.return_value = {
                        "report_path": str(agent2_report_path),
                        "outputs": {
                            "risk_flags": str(processed_dir / "agent2_risk_flags.parquet"),
                            "risk_scores": str(processed_dir / "agent2_risk_scores.parquet"),
                            "supplier_risk_summary": str(
                                processed_dir / "agent2_supplier_risk_summary.parquet"
                            ),
                            "model_comparison": str(
                                processed_dir / "agent2_model_comparison.parquet"
                            ),
                        },
                    }
                    result = run_batch(
                        run_mode="weekly",
                        year=2024,
                        cpv_prefix="71",
                        force=False,
                        place_download=False,
                        place_datasets=["place_profiles"],
                        include_datos_gob=False,
                        boe_input=boe_input,
                        open_tender_input=open_tender_input,
                        raw_dir=raw_dir,
                        processed_dir=processed_dir,
                        manifest_path=manifest_path,
                        batch_state_path=processed_dir / "run_batch_state.json",
                        batch_manifest_dir=workspace / "data/manifest/batches",
                    )

            self.assertTrue(run_agent1_mock.called)
            self.assertTrue(run_agent2_mock.called)
            self.assertEqual(result["status"], "executed")
            self.assertTrue(result["agent1_executed"])
            self.assertTrue(result["agent2_executed"])
            self.assertEqual(result["agent2_report"]["report_path"], str(agent2_report_path))


if __name__ == "__main__":
    unittest.main()
