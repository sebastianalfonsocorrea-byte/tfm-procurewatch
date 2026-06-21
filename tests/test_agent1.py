from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import unittest
from unittest import mock

from procurewatch.agent1 import run_agent1
from procurewatch.agent1 import build_agent1_quality_summary
from procurewatch.agent1 import build_agent2_canonical_dataset
from procurewatch.agent1 import build_source_coverage


@dataclass
class _FakeTarget:
    id: str
    kind: str
    output_path: Path


class Agent1Tests(unittest.TestCase):
    def test_run_agent1_can_download_place_inputs_when_not_provided(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            boe_input = workspace / "boe.csv"
            opentender_input = workspace / "opentender.zip"
            boe_input.write_text("cabezera\n")
            opentender_input.write_text("dummy")

            downloaded_file = workspace / "fake-place.zip"
            downloaded_file.write_text("zip-content")
            fake_targets = [
                _FakeTarget(
                    id="place_profiles",
                    kind="dataset",
                    output_path=downloaded_file,
                )
            ]

            fake_modules = {
                "procurewatch.data_sources.place": SimpleNamespace(
                    load_manifest=lambda _path: {"datasets": []},
                    build_targets=lambda *args, **kwargs: fake_targets,
                    download_targets=lambda *_args, **_kwargs: [{"ok": True}],
                ),
                "procurewatch.data_sources.boe": SimpleNamespace(
                    normalize_boe_file=lambda *args, **kwargs: {"out": "boe"},
                ),
                "procurewatch.data_sources.place_normalize": SimpleNamespace(
                    normalize_place_archives=lambda *args, **kwargs: {"out": "place"},
                ),
                "procurewatch.data_sources.opentender": SimpleNamespace(
                    normalize_opentender_file=lambda *args, **kwargs: {"out": "ot"},
                ),
            }
            with (
                mock.patch.dict("sys.modules", fake_modules),
                mock.patch("procurewatch.agent1.build_source_coverage", return_value={"ok": True}),
            ):
                report = run_agent1(
                    boe_input=boe_input,
                    open_tender_input=opentender_input,
                    place_inputs=[],
                    place_download=True,
                    output_dir=workspace / "processed",
                )

            self.assertIn("agent1_run_report_path", report)
            self.assertIn("place_inputs", report["inputs"])
            self.assertEqual(report["inputs"]["place_inputs"], [str(downloaded_file)])

    def test_run_agent1_requires_place_inputs_without_download(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            boe_input = workspace / "boe.csv"
            opentender_input = workspace / "opentender.zip"
            boe_input.write_text("cabezera\n")
            opentender_input.write_text("dummy")

            with self.assertRaises(ValueError):
                run_agent1(
                    boe_input=boe_input,
                    open_tender_input=opentender_input,
                    place_inputs=[],
                    place_download=False,
                )

    def test_agent1_builds_coverage_canonical_dataset_and_quality_summary(self) -> None:
        import pandas as pd

        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            processed = workspace / "processed"
            processed.mkdir()
            pd.DataFrame(
                [
                    {
                        "contract_id": "boe-1",
                        "file_number": "EXP-1",
                        "institution": "Inst",
                        "buyer_name": "Ayuntamiento Norte",
                        "publication_date": "2024-01-01",
                        "supplier_name": "Proveedor A",
                        "object": "Servicio de ingenieria",
                        "procedure": "Abierto",
                        "estimated_value_eur": 100.0,
                        "awarded_value_eur": 90.0,
                        "cpv_codes_raw": "71300000",
                        "cpv_code_list": ["71300000"],
                        "source_file": "boe.csv",
                    }
                ]
            ).to_parquet(processed / "contracts_boe_cpv71.parquet", index=False)
            pd.DataFrame(
                [
                    {
                        "source_entry_id": "place-1",
                        "source_dataset": "profiles",
                        "contract_folder_id": "EXP-1",
                        "buyer_name": "Ayuntamiento Norte",
                        "buyer_dir3": "L010000",
                        "published_date": "2024-01-01",
                        "winning_party_name": "Proveedor A",
                        "winning_party_nif": "A00000000",
                        "contract_title": "Servicio de ingenieria",
                        "procedure_code": "open",
                        "award_date": "2024-02-01",
                        "estimated_overall_amount": 100.0,
                        "total_amount": 90.0,
                        "cpv_codes_raw": "71300000",
                        "cpv_code_list": ["71300000"],
                        "source_file": "place.zip",
                    }
                ]
            ).to_parquet(processed / "contracts_place_cpv71.parquet", index=False)
            pd.DataFrame(
                [
                    {
                        "source_record_id": "ot-1",
                        "source_entry_id": "ot-uri",
                        "source_file": "data-es-ocds-2024.json",
                        "buyer_name": "Ayuntamiento Norte",
                        "buyer_id": "buyer-1",
                        "publication_date": "2024-01-01",
                        "awarded_supplier_name": "Proveedor A",
                        "awarded_supplier_nif": "A00000000",
                        "contract_title": "Servicio de ingenieria",
                        "procedure_code": "open",
                        "award_date": "2024-02-01",
                        "estimated_amount_raw": 100.0,
                        "awarded_amount_raw": 90.0,
                        "cpv_codes_raw": "71300000",
                        "cpv_code_list": ["71300000"],
                    }
                ]
            ).to_parquet(processed / "contracts_opentender_2024_cpv71.parquet", index=False)

            coverage = build_source_coverage(output_dir=processed, cpv_prefix="71", year=2024)
            canonical = build_agent2_canonical_dataset(output_dir=processed, cpv_prefix="71", year=2024)
            quality = build_agent1_quality_summary(output_dir=processed, coverage=coverage, canonical=canonical)

            self.assertTrue((processed / "agent1_contract_key_coverage.parquet").exists())
            self.assertTrue((processed / "agent2_contracts_canonical.parquet").exists())
            self.assertTrue((processed / "agent2_contracts_canonical_schema.json").exists())
            self.assertEqual(canonical["rows"], 3)
            self.assertIn(quality["status"], {"ok", "warning"})

    def test_run_agent1_reuses_cached_source_outputs(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            processed = workspace / "processed"
            processed.mkdir()
            boe_input = workspace / "boe.csv"
            opentender_input = workspace / "opentender.zip"
            place_input = workspace / "place.zip"
            boe_input.write_text("boe")
            opentender_input.write_text("opentender")
            place_input.write_text("place")

            for name in [
                "contracts_boe.parquet",
                "contracts_boe_cpv71.parquet",
                "contracts_place.parquet",
                "contracts_place_cpv71.parquet",
                "contracts_opentender_2024.parquet",
                "contracts_opentender_2024_cpv71.parquet",
            ]:
                (processed / name).write_bytes(b"cached")

            sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            (processed / "data_quality_report.json").write_text(
                json.dumps({"source": {"sha256": sha(boe_input)}}),
                encoding="utf-8",
            )
            (processed / "contracts_place_quality.json").write_text(
                json.dumps({"source_files": [str(place_input)]}),
                encoding="utf-8",
            )
            (processed / "contracts_opentender_2024_quality.json").write_text(
                json.dumps({"source": {"sha256": sha(opentender_input), "requested_year": 2024}}),
                encoding="utf-8",
            )

            fake_modules = {
                "procurewatch.data_sources.boe": SimpleNamespace(
                    PARSER_VERSION="test",
                    normalize_boe_file=mock.Mock(side_effect=AssertionError("boe should be cached")),
                ),
                "procurewatch.data_sources.place_normalize": SimpleNamespace(
                    PARSER_VERSION="test",
                    normalize_place_archives=mock.Mock(side_effect=AssertionError("place should be cached")),
                ),
                "procurewatch.data_sources.opentender": SimpleNamespace(
                    PARSER_VERSION="test",
                    normalize_opentender_file=mock.Mock(side_effect=AssertionError("opentender should be cached")),
                ),
            }
            with (
                mock.patch.dict("sys.modules", fake_modules),
                mock.patch("procurewatch.agent1.build_source_coverage", return_value={"contract_key_coverage_path": str(processed / "coverage.parquet")}),
                mock.patch("procurewatch.agent1.build_agent2_canonical_dataset", return_value={"path": str(processed / "agent2.parquet"), "schema_path": str(processed / "schema.json"), "rows": 1}),
                mock.patch(
                    "procurewatch.agent1.analytical_dataset.build_analytical_datasets",
                    return_value={
                        "contracts_path": str(processed / "contracts_analytical.parquet"),
                        "contracts_rows": 1,
                        "suppliers_path": str(processed / "suppliers_analytical.parquet"),
                        "suppliers_rows": 1,
                    },
                ),
                mock.patch("procurewatch.agent1.build_agent1_quality_summary", return_value={"status": "ok"}),
            ):
                report = run_agent1(
                    boe_input=boe_input,
                    open_tender_input=opentender_input,
                    place_inputs=[place_input],
                    output_dir=processed,
                )

            self.assertTrue(report["boe"]["cached"])
            self.assertTrue(report["place"]["cached"])
            self.assertTrue(report["opentender"]["cached"])

    def test_agent1_quality_summary_reports_required_tfm_metrics(self) -> None:
        import pandas as pd

        with TemporaryDirectory() as temp:
            processed = Path(temp)
            canonical_path = processed / "agent2_contracts_canonical.parquet"
            schema_path = processed / "agent2_contracts_canonical_schema.json"
            coverage_path = processed / "agent1_contract_key_coverage.parquet"
            schema_path.write_text("{}")
            coverage_path.write_bytes(b"coverage")
            pd.DataFrame(
                [
                    {
                        "contract_key_canon": "contract-1",
                        "source": "place",
                        "buyer_name": "Organismo A",
                        "publication_date": "2024-01-01",
                        "award_date": "2024-01-15",
                        "supplier_id": "B99286320",
                        "cpv_codes_raw": "71300000",
                    },
                    {
                        "contract_key_canon": "contract-2",
                        "source": "place",
                        "buyer_name": "Organismo A",
                        "publication_date": "2024-02-10",
                        "award_date": "2024-02-01",
                        "supplier_id": "INVALIDO",
                        "cpv_codes_raw": "71300000",
                    },
                    {
                        "contract_key_canon": "contract-3",
                        "source": "boe",
                        "buyer_name": "Organismo B",
                        "publication_date": "",
                        "award_date": "",
                        "supplier_id": "",
                        "cpv_codes_raw": "71300000",
                    },
                ]
            ).to_parquet(canonical_path, index=False)

            summary = build_agent1_quality_summary(
                output_dir=processed,
                coverage={"contract_key_coverage_path": str(coverage_path)},
                canonical={
                    "path": str(canonical_path),
                    "schema_path": str(schema_path),
                    "rows": 3,
                },
            )

            metrics = summary["quality_metrics"]
            self.assertEqual(metrics["ocds_critical_completeness"]["complete_rows"], 2)
            self.assertEqual(metrics["supplier_tax_id"]["valid"], 1)
            self.assertEqual(metrics["supplier_tax_id"]["invalid"], 1)
            self.assertEqual(metrics["supplier_tax_id"]["missing"], 1)
            self.assertEqual(metrics["temporal_coherence"]["comparable_rows"], 2)
            self.assertEqual(metrics["temporal_coherence"]["coherent_rows"], 1)
            self.assertEqual(metrics["temporal_coherence"]["incoherent_rows"], 1)
            self.assertEqual(summary["status"], "warning")


if __name__ == "__main__":
    unittest.main()
