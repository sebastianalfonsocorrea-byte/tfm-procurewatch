from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import gzip
import json
import zipfile
import unittest
from unittest import mock

from procurewatch.data_sources.opentender import discover_opentender_download_url
from procurewatch.data_sources.opentender import download_opentender_zip
from procurewatch.data_sources.opentender import normalize_opentender_file


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

        self.assertEqual(url, "https://data.open-contracting.org/downloads/opentender-2024.jsonl.gz")

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

        self.assertEqual(url, "https://data.open-contracting.org/downloads/opentender-2024.jsonl.gz")

    def test_download_opentender_zip_uses_real_extension_for_jsonl_gz(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            output_path = workspace / "data-es-ocds-json.zip"

            download_response = mock.Mock()
            download_response.status_code = 200
            download_response.headers = {"content-type": "application/gzip"}
            download_response.iter_content = mock.Mock(return_value=[b"abc"])
            download_response.raise_for_status = mock.Mock()

            with mock.patch(
                "procurewatch.data_sources.opentender.resolve_opentender_download_url",
                return_value="https://data.example.org/opentender-2024.jsonl.gz",
            ), mock.patch(
                "procurewatch.data_sources.opentender.requests.get",
                return_value=download_response,
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
                zf.writestr("data-es-ocds-2024.json", _make_opentender_payload(record_id="ot-1", cpv="71300000"))
                zf.writestr("data-es-ocds-2023.json", _make_opentender_payload(record_id="ot-2", cpv="45100000"))

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
