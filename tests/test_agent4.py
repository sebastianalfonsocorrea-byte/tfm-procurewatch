from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from procurewatch.agent4 import chunk_text, load_text_document
from procurewatch.agent4.schemas import DocumentRef
from procurewatch.agent4.smoke import run_agent4_smoke
from procurewatch.cli import main


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
        with TemporaryDirectory() as temp:
            path = Path(temp) / "sample.txt"
            path.write_text("contenido documental", encoding="utf-8")

            document = load_text_document(path, contract_key_canon="contract-1")

        self.assertTrue(document.document_id.startswith("sample-"))
        self.assertEqual(document.contract_key_canon, "contract-1")
        self.assertEqual(document.metadata["path"], str(path))

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


if __name__ == "__main__":
    unittest.main()
