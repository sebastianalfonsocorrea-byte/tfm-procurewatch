from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
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

            def hash_file(path: Path) -> str:
                return hashlib.sha256(path.read_bytes()).hexdigest()

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
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["agent1_executed"], False)
            self.assertEqual(result["missing_required_inputs"], [])
            self.assertTrue(Path(result["batch_manifest_path"]).exists())
            self.assertTrue(batch_state_path.exists())
            self.assertEqual(
                result["derived_rebuild_plan"]["agent2_mvp"],
                "not_planned_for_weekly_batch",
            )

    def test_batch_writes_manifest_when_required_inputs_are_missing(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            raw_dir = workspace / "data/raw"
            processed_dir = workspace / "data/processed"
            manifest_dir = workspace / "data/manifest/batches"
            raw_dir.mkdir(parents=True)

            with mock.patch("procurewatch.batch.run_agent1") as run_agent1_mock:
                result = run_batch(
                    run_mode="weekly",
                    include_datos_gob=False,
                    boe_input=raw_dir / "missing_boe.csv",
                    open_tender_input=raw_dir / "missing_opentender.zip",
                    raw_dir=raw_dir,
                    processed_dir=processed_dir,
                    manifest_path=workspace / "missing_place_manifest.json",
                    batch_state_path=processed_dir / "run_batch_state.json",
                    batch_manifest_dir=manifest_dir,
                )

            self.assertFalse(run_agent1_mock.called)
            self.assertEqual(result["status"], "blocked_missing_inputs")
            self.assertFalse(result["agent1_executed"])
            self.assertCountEqual(
                [item["source_id"] for item in result["missing_required_inputs"]],
                ["boe_raw", "opentender_raw"],
            )
            self.assertTrue(Path(result["batch_manifest_path"]).exists())
            payload = json.loads(Path(result["batch_manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked_missing_inputs")
            self.assertEqual(payload["derived_rebuild_plan"]["agent1"], "blocked")

    def test_monthly_batch_executes_agent1_when_inputs_are_present(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            raw_dir = workspace / "data/raw"
            processed_dir = workspace / "data/processed"
            raw_dir.mkdir(parents=True)
            boe_input = raw_dir / "boe.csv"
            open_tender_input = raw_dir / "opentender.zip"
            boe_input.write_text("header\n", encoding="utf-8")
            open_tender_input.write_text("zip-content", encoding="utf-8")

            with mock.patch("procurewatch.batch.run_agent1") as run_agent1_mock:
                run_agent1_mock.return_value = {
                    "agent1_run_report_path": str(processed_dir / "agent1_run_report.json")
                }
                result = run_batch(
                    run_mode="monthly",
                    include_datos_gob=False,
                    boe_input=boe_input,
                    open_tender_input=open_tender_input,
                    raw_dir=raw_dir,
                    processed_dir=processed_dir,
                    manifest_path=workspace / "missing_place_manifest.json",
                    batch_state_path=processed_dir / "run_batch_state.json",
                    batch_manifest_dir=workspace / "data/manifest/batches",
                )

            run_agent1_mock.assert_called_once()
            self.assertEqual(result["status"], "executed")
            self.assertTrue(result["agent1_executed"])
            self.assertEqual(
                result["derived_rebuild_plan"]["agent2_mvp"],
                "planned_if_canonical_exists",
            )

    def test_missing_place_without_download_blocks_batch_with_warning(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            raw_dir = workspace / "data/raw"
            processed_dir = workspace / "data/processed"
            raw_dir.mkdir(parents=True)
            boe_input = raw_dir / "boe.csv"
            open_tender_input = raw_dir / "opentender.zip"
            boe_input.write_text("header\n", encoding="utf-8")
            open_tender_input.write_text("zip-content", encoding="utf-8")
            manifest_path = _write_place_manifest(workspace)

            with mock.patch("procurewatch.batch.run_agent1") as run_agent1_mock:
                result = run_batch(
                    run_mode="weekly",
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

            self.assertFalse(run_agent1_mock.called)
            self.assertEqual(result["status"], "blocked_missing_inputs")
            self.assertIn("place::place_profiles", result["changed_sources"])
            self.assertIn(
                "place::place_profiles",
                [item["source_id"] for item in result["missing_required_inputs"]],
            )
            self.assertTrue(any("PLACE local" in warning for warning in result["warnings"]))


def _write_place_manifest(workspace: Path) -> Path:
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
    return manifest_path


if __name__ == "__main__":
    unittest.main()
