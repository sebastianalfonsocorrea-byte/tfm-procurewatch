from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from uuid import uuid4

from procurewatch.agent4 import (
    chunk_text,
    load_corpus_documents,
    load_html_document,
    load_text_document,
    write_documents_manifest,
)
from procurewatch.agent4.schemas import DocumentRef
from procurewatch.agent4.smoke import run_agent4_smoke
from procurewatch.cli import main


def _test_workspace(name: str) -> Path:
    path = Path("data/processed/agent4_test_artifacts") / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Agent4Tests(unittest.TestCase):
    def test_chunk_text_is_deterministic_and_keeps_payload_keys(self) -> None:
        document = DocumentRef(
            document_id="doc-1",
            source="test",
            text="uno dos tres cuatro cinco seis siete ocho nueve diez",
            contract_key_canon="contract-1",
        )

        chunks = chunk_text(document, chunk_size=18, overlap=4)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_id, "doc-1:0")
        self.assertEqual(chunks[0].contract_key_canon, "contract-1")
        self.assertIn("text_hash", chunks[0].payload())

    def test_load_text_document_builds_stable_document_ref(self) -> None:
        temp = _test_workspace("loader")
        path = temp / "sample.txt"
        path.write_text("contenido documental", encoding="utf-8")

        document = load_text_document(path, contract_key_canon="contract-1")

        self.assertTrue(document.document_id.startswith("sample-"))
        self.assertEqual(document.contract_key_canon, "contract-1")
        self.assertEqual(document.metadata["path"], str(path))
        self.assertEqual(document.metadata["text_hash"], document.text_hash)

    def test_load_html_document_extracts_text_and_metadata(self) -> None:
        temp = _test_workspace("html")
        path = temp / "sample.html"
        path.write_text(
            "<html><body><h1>Titulo</h1><p>Evidencia documental</p>"
            "<script>ignored()</script></body></html>",
            encoding="utf-8",
        )

        document = load_html_document(path, contract_key_canon="contract-html")

        self.assertEqual(document.document_type, "html")
        self.assertEqual(document.contract_key_canon, "contract-html")
        self.assertIn("Titulo", document.text)
        self.assertIn("Evidencia documental", document.text)
        self.assertNotIn("ignored", document.text)
        self.assertIn("html_parser", document.metadata)

    def test_synthetic_corpus_loads_documents_and_manifest(self) -> None:
        documents = load_corpus_documents(
            Path("data/synthetic/agent4_corpus/agent4_corpus_index.json")
        )
        output_path = _test_workspace("manifest") / "agent4_documents_manifest.json"

        manifest = write_documents_manifest(documents, output_path)
        payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(len(documents), 3)
        self.assertEqual(payload["dataset"], "agent4_documents_manifest")
        self.assertEqual(manifest["documents_count"], 3)
        for item in payload["documents"]:
            self.assertTrue(item["document_id"])
            self.assertTrue(item["contract_key_canon"])
            self.assertTrue(item["source"])
            self.assertTrue(item["source_record_id"])
            self.assertTrue(item["document_type"])
            self.assertTrue(item["text_hash"])
            self.assertTrue(item["path"])

    def test_agent4_smoke_without_services_returns_ok(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = run_agent4_smoke(check_services=False)

        self.assertEqual(exit_code, 0)
        self.assertIn("Agent4 smoke", output.getvalue())

    def test_cli_agent4_smoke_command(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["agent4-smoke"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Chunks generados", output.getvalue())

    def test_cli_agent4_build_manifest_command(self) -> None:
        output = io.StringIO()
        output_path = _test_workspace("cli-manifest") / "manifest.json"

        with redirect_stdout(output):
            exit_code = main(["agent4-build-manifest", "--output", str(output_path)])

        self.assertEqual(exit_code, 0)
        self.assertTrue(output_path.exists())
        self.assertIn("Manifiesto Agent4 generado", output.getvalue())


if __name__ == "__main__":
    unittest.main()
