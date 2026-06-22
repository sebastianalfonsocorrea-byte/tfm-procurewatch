from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from procurewatch.agent4 import (
    Agent4IndexReport,
    DeterministicEmbeddingClient,
    DocumentChunk,
    EmbeddingMetadata,
    OllamaEmbeddingClient,
    QdrantSearchFilters,
    QdrantVectorStore,
    chunk_text,
    keyword_retrieve,
    load_corpus_documents,
    load_html_document,
    load_text_document,
    write_documents_manifest,
)
from procurewatch.agent4.qdrant_store import build_filter_conditions, build_qdrant_points
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

    def test_chunk_text_returns_empty_for_blank_text(self) -> None:
        document = DocumentRef(document_id="doc-empty", source="test", text=" \n\t ")

        self.assertEqual(chunk_text(document), [])

    def test_chunk_text_short_text_keeps_complete_payload(self) -> None:
        document = DocumentRef(
            document_id="doc-short",
            source="synthetic",
            text=" contrato menor ",
            contract_key_canon="contract-short",
            source_record_id="record-short",
            document_type="text",
        )

        chunks = chunk_text(document, chunk_size=100, overlap=10)
        payload = chunks[0].payload()

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "contrato menor")
        self.assertEqual(payload["chunk_id"], "doc-short:0")
        self.assertEqual(payload["document_id"], "doc-short")
        self.assertEqual(payload["contract_key_canon"], "contract-short")
        self.assertEqual(payload["source"], "synthetic")
        self.assertEqual(payload["source_record_id"], "record-short")
        self.assertEqual(payload["document_type"], "text")
        self.assertEqual(len(str(payload["text_hash"])), 64)

    def test_chunk_text_long_text_uses_deterministic_overlap(self) -> None:
        document = DocumentRef(document_id="doc-long", source="test", text="abcdefghij")

        first_run = chunk_text(document, chunk_size=5, overlap=2)
        second_run = chunk_text(document, chunk_size=5, overlap=2)

        self.assertEqual([chunk.text for chunk in first_run], [chunk.text for chunk in second_run])
        self.assertEqual(first_run[0].text[-2:], first_run[1].text[:2])
        self.assertEqual(first_run[1].text[-2:], first_run[2].text[:2])

    def test_chunk_text_rejects_invalid_parameters(self) -> None:
        document = DocumentRef(document_id="doc-invalid", source="test", text="contenido")

        with self.assertRaises(ValueError):
            chunk_text(document, chunk_size=0)
        with self.assertRaises(ValueError):
            chunk_text(document, overlap=-1)
        with self.assertRaises(ValueError):
            chunk_text(document, chunk_size=10, overlap=10)

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

    def test_keyword_retrieve_returns_empty_for_empty_or_unmatched_inputs(self) -> None:
        chunk = DocumentChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            text="evidencia documental",
            chunk_index=0,
        )

        self.assertEqual(keyword_retrieve([], "evidencia"), [])
        self.assertEqual(keyword_retrieve([chunk], ""), [])
        self.assertEqual(keyword_retrieve([chunk], "!!!"), [])
        self.assertEqual(keyword_retrieve([chunk], "contrato", limit=0), [])
        self.assertEqual(keyword_retrieve([chunk], "contrato"), [])

    def test_keyword_retrieve_scores_orders_and_limits_results(self) -> None:
        chunks = [
            DocumentChunk(
                chunk_id="doc-b:0",
                document_id="doc-b",
                text="riesgo contrato",
                chunk_index=0,
            ),
            DocumentChunk(
                chunk_id="doc-a:0",
                document_id="doc-a",
                text="riesgo evidencia contrato",
                chunk_index=0,
            ),
            DocumentChunk(
                chunk_id="doc-c:0",
                document_id="doc-c",
                text="evidencia riesgo adicional",
                chunk_index=0,
            ),
        ]

        results = keyword_retrieve(chunks, "riesgo evidencia", limit=2)

        self.assertEqual([result.chunk.chunk_id for result in results], ["doc-a:0", "doc-c:0"])
        self.assertEqual(results[0].score, 1.0)
        self.assertEqual(results[1].score, 1.0)

    def test_deterministic_embedding_client_returns_stable_dimensions(self) -> None:
        client = DeterministicEmbeddingClient(dimension=8)

        first = client.embed_texts(["contrato", "evidencia"])
        second = client.embed_texts(["contrato", "evidencia"])

        self.assertEqual(first.metadata.provider, "deterministic")
        self.assertEqual(first.metadata.dimension, 8)
        self.assertEqual(len(first.vectors), 2)
        self.assertEqual(len(first.vectors[0]), 8)
        self.assertEqual(first.vectors, second.vectors)

    def test_ollama_embedding_client_parses_embed_response(self) -> None:
        client = OllamaEmbeddingClient(base_url="http://ollama.test", model="embed-test")
        client._post_json = lambda _path, _payload: {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

        batch = client.embed_texts(["uno", "dos"])

        self.assertEqual(batch.metadata.provider, "ollama")
        self.assertEqual(batch.metadata.model, "embed-test")
        self.assertEqual(batch.metadata.dimension, 2)
        self.assertEqual(batch.vectors, [[0.1, 0.2], [0.3, 0.4]])

    def test_qdrant_points_include_chunk_payload_and_embedding_metadata(self) -> None:
        chunk = DocumentChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            text="evidencia documental",
            chunk_index=0,
            contract_key_canon="contract-1",
        )
        metadata = EmbeddingMetadata(
            provider="deterministic",
            model="test-model",
            dimension=2,
            indexed_at="2026-06-23T00:00:00+00:00",
        )

        points = build_qdrant_points([chunk], [[0.1, 0.2]], metadata)

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["vector"], [0.1, 0.2])
        self.assertEqual(points[0]["payload"]["chunk_id"], "doc-1:0")
        self.assertEqual(points[0]["payload"]["contract_key_canon"], "contract-1")
        self.assertEqual(points[0]["payload"]["embedding_provider"], "deterministic")
        self.assertEqual(points[0]["payload"]["embedding_dimension"], 2)

    def test_qdrant_filter_conditions_are_built_from_supported_filters(self) -> None:
        filters = QdrantSearchFilters(
            contract_key_canon="contract-1",
            source="synthetic",
            document_type="html",
        )

        conditions = build_filter_conditions(filters)

        self.assertEqual(
            conditions,
            [
                {"key": "contract_key_canon", "value": "contract-1"},
                {"key": "source", "value": "synthetic"},
                {"key": "document_type", "value": "html"},
            ],
        )

    def test_qdrant_store_upserts_and_searches_with_fake_client(self) -> None:
        fake_client = _FakeQdrantClient()
        store = QdrantVectorStore(
            url="http://qdrant.test",
            collection_name="procurement_documents",
            client=fake_client,
        )
        chunk = DocumentChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            text="evidencia documental",
            chunk_index=0,
            contract_key_canon="contract-1",
            source="synthetic",
            document_type="text",
        )
        metadata = EmbeddingMetadata(
            provider="deterministic",
            model="test-model",
            dimension=2,
            indexed_at="2026-06-23T00:00:00+00:00",
        )

        report = store.upsert_chunks([chunk], [[0.1, 0.2]], metadata)
        results = store.search(
            [0.1, 0.2],
            filters=QdrantSearchFilters(contract_key_canon="contract-1"),
        )

        self.assertEqual(report.points_count, 1)
        self.assertEqual(fake_client.upserted_collection, "procurement_documents")
        if isinstance(fake_client.search_filter, dict):
            self.assertEqual(fake_client.search_filter["must"][0]["key"], "contract_key_canon")
        else:
            self.assertEqual(fake_client.search_filter.must[0].key, "contract_key_canon")
        self.assertEqual(results[0].chunk.chunk_id, "doc-1:0")
        self.assertEqual(results[0].score, 0.92)

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

    def test_cli_agent4_index_corpus_command_uses_indexing_flow(self) -> None:
        output = io.StringIO()
        report = Agent4IndexReport(
            collection_name="procurement_documents",
            documents_count=3,
            chunks_count=4,
            points_count=4,
            embedding_provider="deterministic",
            embedding_model="test-model",
            embedding_dimension=8,
            results=[
                type(
                    "Result",
                    (),
                    {
                        "chunk": DocumentChunk(
                            chunk_id="doc-1:0",
                            document_id="doc-1",
                            text="evidencia",
                            chunk_index=0,
                            contract_key_canon="contract-1",
                        ),
                        "score": 0.95,
                    },
                )()
            ],
        )

        with patch("procurewatch.agent4.index_corpus_to_qdrant", return_value=report) as mocked:
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "agent4-index-corpus",
                        "--query",
                        "evidencia",
                        "--contract-key",
                        "contract-1",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("Corpus Agent4 indexado en Qdrant", output.getvalue())
        self.assertIn("Resultados query: 1", output.getvalue())
        self.assertEqual(mocked.call_args.kwargs["filters"].contract_key_canon, "contract-1")


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.upserted_collection = None
        self.upserted_points = []
        self.search_filter = None

    def collection_exists(self, *, collection_name: str) -> bool:
        return True

    def upsert(self, *, collection_name: str, points: list[dict[str, object]]) -> None:
        self.upserted_collection = collection_name
        self.upserted_points = points

    def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        query_filter: object,
        limit: int,
    ) -> list[object]:
        self.search_filter = query_filter
        point = self.upserted_points[0]
        payload = point["payload"] if isinstance(point, dict) else point.payload
        return [SimpleNamespace(payload=payload, score=0.92)]


if __name__ == "__main__":
    unittest.main()
