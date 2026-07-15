from __future__ import annotations

import gzip
import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from procurewatch.data_sources.opentender import (
    discover_opentender_download_url,
    download_opentender_zip,
    normalize_opentender_file,
)


def _make_opentender_payload(*, record_id: str, cpv: str, date: str = "2024-01-01") -> str:
    return json.dumps(
        {
            "uri": f"https://example.org/{record_id}",
            "metaData": {"lastModified": "2024-01-02T00:00:00Z"},
            "releases": [
                {
                    "id": record_id,
                    "date": date,
                    "title": f"Contrato {record_id}",
                    "buyer": {
                        "name": "Ministerio de Pruebas",
                        "id": "buyer-1",
                        "additionalIdentifiers": [{"scheme": "NIF", "id": "B12345678"}],
                    },
                    "tender": {
                        "title": f"Contrato {record_id}",
                        "procurementMethod": "open",
                        "items": [{"classification": {"id": cpv}}],
                        "value": {"amount": "100", "currency": "EUR"},
                    },
                    "awards": [
                        {
                            "date": "2024-01-05",
                            "suppliers": [
                                {
                                    "name": "Proveedor A",
                                    "id": "supplier-1",
                                    "additionalIdentifiers": [{"scheme": "NIF", "id": "A12345678"}],
                                }
                            ],
                            "value": {"amount": "90", "currency": "EUR"},
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )


def _make_compiled_opentender_payload(
    *, record_id: str, cpv: str, date: str = "2024-01-01"
) -> dict:
    return {
        "id": record_id,
        "tag": ["compiled"],
        "ocid": record_id.rsplit("-", 1)[0],
        "date": date,
        "buyer": {
            "id": "buyer-1",
            "name": "Ministerio de Pruebas",
        },
        "tender": {
            "id": "tender-1",
            "title": "Contrato de prueba",
            "items": [
                {"id": "item-1", "classification": {"id": cpv, "scheme": "CPV"}},
            ],
            "value": {"amount": "100", "currency": "EUR"},
            "procurementMethod": "open",
            "mainProcurementCategory": "services",
        },
        "awards": [
            {
                "id": "award-1",
                "date": "2024-01-05",
                "value": {"amount": "90", "currency": "EUR"},
                "suppliers": [
                    {
                        "id": "supplier-1",
                        "name": "Proveedor A",
                    }
                ],
            }
        ],
        "metaData": {"lastModified": "2024-01-02T00:00:00Z"},
    }


class OpenTenderTests(unittest.TestCase):
    def test_discover_opentender_download_url_prefers_jsonl_gz(self) -> None:
        html = """
        <html>
          <body>
            <a href="/downloads/opentender-2024.csv">CSV</a>
            <a href="/downloads/opentender-2024.jsonl.gz">JSON</a>
            <a href="/downloads/opentender-all.jsonl.gz">All years</a>
          </body>
        </html>
        """
        response = mock.Mock()
        response.text = html
        response.url = "https://data.open-contracting.org/en/publication/94"
        response.raise_for_status = mock.Mock()

        with mock.patch("procurewatch.data_sources.opentender.requests.get", return_value=response):
            url = discover_opentender_download_url(
                page_url="https://data.open-contracting.org/en/publication/94",
                year=2024,
            )

        self.assertEqual(
            url, "https://data.open-contracting.org/downloads/opentender-2024.jsonl.gz"
        )

    def test_resolve_opentender_download_url_uses_spanish_page_first(self) -> None:
        response = mock.Mock()
        response.text = "<html><body></body></html>"
        response.url = "https://opentender.eu/es/download"
        response.raise_for_status = mock.Mock()

        with mock.patch(
            "procurewatch.data_sources.opentender.requests.get",
            side_effect=[
                response,
                self._make_registry_response(),
            ],
        ):
            from procurewatch.data_sources.opentender import resolve_opentender_download_url

            url = resolve_opentender_download_url("https://opentender.eu/es/download", year=2024)

        self.assertEqual(
            url, "https://data.open-contracting.org/downloads/opentender-2024.jsonl.gz"
        )

    def test_download_opentender_zip_uses_real_extension_for_jsonl_gz(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            output_path = workspace / "data-es-ocds-json.zip"

            download_response = mock.Mock()
            download_response.status_code = 200
            download_response.headers = {"content-type": "application/gzip"}
            download_response.iter_content = mock.Mock(return_value=[b"abc"])
            download_response.raise_for_status = mock.Mock()

            with (
                mock.patch(
                    "procurewatch.data_sources.opentender.resolve_opentender_download_url",
                    return_value="https://data.example.org/opentender-2024.jsonl.gz",
                ),
                mock.patch(
                    "procurewatch.data_sources.opentender.requests.get",
                    return_value=download_response,
                ),
            ):
                report = download_opentender_zip(
                    url="https://data.open-contracting.org/en/publication/94",
                    output_path=output_path,
                    overwrite=True,
                )

            self.assertTrue(report["output_path"].endswith(".jsonl.gz"))
            self.assertTrue(Path(report["output_path"]).exists())

    def test_normalize_opentender_file_reads_jsonl_gz(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            input_path = workspace / "opentender.jsonl.gz"
            output_dir = workspace / "processed"
            output_dir.mkdir()

            lines = [
                _make_opentender_payload(record_id="ot-1", cpv="71300000"),
                _make_opentender_payload(record_id="ot-2", cpv="45100000"),
            ]
            with gzip.open(input_path, "wt", encoding="utf-8") as handle:
                handle.write("\n".join(lines))

            report = normalize_opentender_file(
                input_path=input_path,
                output_dir=output_dir,
                cpv_prefix="all",
            )

            self.assertEqual(report["rows"]["parsed_records"], 2)
            self.assertEqual(report["rows"]["cpv71_rows"], 1)
            self.assertTrue((output_dir / "contracts_opentender_all.parquet").exists())
            self.assertTrue((output_dir / "contracts_opentender_all_cpvall.parquet").exists())

    def test_parse_opentender_record_handles_compiled_payload(self) -> None:
        from procurewatch.data_sources.opentender import parse_opentender_record

        record = parse_opentender_record(
            _make_compiled_opentender_payload(record_id="ocds-123-2024-01-01", cpv="71300000"),
            source_year=2024,
            source_file="data-es-ocds-json.jsonl.gz",
        )

        self.assertEqual(record.source_record_id, "ocds-123-2024-01-01")
        self.assertEqual(record.buyer_name, "Ministerio de Pruebas")
        self.assertEqual(record.cpv_code_list, ["71300000"])
        self.assertTrue(record.is_cpv_71)
        self.assertEqual(record.awarded_supplier_name, "Proveedor A")
        self.assertEqual(record.publication_date, "2024-01-01")

    @staticmethod
    def _make_registry_response() -> mock.Mock:
        response = mock.Mock()
        response.text = """
        <html>
          <body>
            <a href="/downloads/opentender-2024.jsonl.gz">JSON</a>
          </body>
        </html>
        """
        response.url = "https://data.open-contracting.org/en/publication/94"
        response.raise_for_status = mock.Mock()
        return response

    def test_normalize_opentender_file_reads_zip(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            input_path = workspace / "opentender.zip"
            output_dir = workspace / "processed"
            output_dir.mkdir()

            with zipfile.ZipFile(input_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(
                    "data-es-ocds-2024.json",
                    _make_opentender_payload(record_id="ot-1", cpv="71300000"),
                )
                zf.writestr(
                    "data-es-ocds-2023.json",
                    _make_opentender_payload(record_id="ot-2", cpv="45100000"),
                )

            report = normalize_opentender_file(
                input_path=input_path,
                output_dir=output_dir,
                year=2024,
                cpv_prefix="71",
            )

            self.assertEqual(report["rows"]["parsed_records"], 1)
            self.assertEqual(report["rows"]["cpv71_rows"], 1)
            self.assertTrue((output_dir / "contracts_opentender_2024.parquet").exists())
            self.assertTrue((output_dir / "contracts_opentender_2024_cpv71.parquet").exists())


if __name__ == "__main__":
    unittest.main()
