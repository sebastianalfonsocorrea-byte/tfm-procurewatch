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
    Agent4EvalCase,
    Agent4IndexReport,
    DeterministicEmbeddingClient,
    DocumentChunk,
    EmbeddingMetadata,
    GenerationResult,
    OllamaEmbeddingClient,
    QdrantSearchFilters,
    QdrantVectorStore,
    build_agent4_capabilities,
    build_agent4_source_registry,
    build_boe_html_fetch_report,
    chunk_text,
    evaluate_agent4_case_state,
    extract_boe_b_id,
    fetch_boe_html_document,
    keyword_retrieve,
    load_corpus_documents,
    load_html_document,
    load_text_document,
    run_agent4_case_context,
    run_agent4_case_flow,
    run_agent4_evaluation,
    run_agent4_graph,
    write_agent4_source_registry,
    write_documents_manifest,
)
from procurewatch.agent4.qdrant_store import (
    _RestQdrantClient,
    build_filter_conditions,
    build_qdrant_points,
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

    def test_agent4_source_registry_documents_scope_and_official_sources(self) -> None:
        output_path = _test_workspace("source-registry") / "agent4_source_registry.json"

        registry = write_agent4_source_registry(output_path)
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        source_ids = {source["source_id"] for source in registry["sources"]}

        self.assertEqual(payload["dataset"], "agent4_source_registry")
        self.assertEqual(payload["source_count"], len(registry["sources"]))
        self.assertIn("boe_html_individual", source_ids)
        self.assertIn("placsp_buyer_profiles", source_ids)
        self.assertIn(
            "No hace crawling",
            " ".join(payload["capabilities"]["document_source_policy"]),
        )
        self.assertIn(
            "Descarga anuncios BOE-B HTML individuales",
            " ".join(payload["capabilities"]["implemented_in_mvp"]),
        )
        self.assertIn(
            "Scraping en vivo masivo",
            " ".join(payload["capabilities"]["not_implemented_in_mvp"]),
        )

    def test_agent4_capabilities_are_reusable_in_artifacts(self) -> None:
        capabilities = build_agent4_capabilities()
        registry = build_agent4_source_registry()

        self.assertIn("Agent4 es el agente documental/RAG", capabilities["scope"])
        self.assertGreaterEqual(registry["source_count"], 10)
        self.assertEqual(registry["capabilities"]["scope"], capabilities["scope"])

    def test_extract_boe_b_id_accepts_only_official_boe_html_urls(self) -> None:
        self.assertEqual(
            extract_boe_b_id("https://www.boe.es/diario_boe/txt.php?id=BOE-B-2024-12345"),
            "BOE-B-2024-12345",
        )

        invalid_urls = [
            "http://www.boe.es/diario_boe/txt.php?id=BOE-B-2024-12345",
            "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-12345",
            "https://example.org/diario_boe/txt.php?id=BOE-B-2024-12345",
            "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2024-12345&x=1",
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    extract_boe_b_id(url)

    def test_fetch_boe_html_document_downloads_mocked_html_and_loads_text(self) -> None:
        temp = _test_workspace("boe-fetch")
        url = "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2024-12345"

        with patch(
            "procurewatch.agent4.boe_fetch.urlopen",
            return_value=_FakeHttpResponse(),
        ) as mocked:
            document = fetch_boe_html_document(
                url=url,
                contract_key_canon="PW-2024-BOE",
                output_dir=temp,
            )

        report = build_boe_html_fetch_report(document)

        self.assertEqual(document.source, "boe_html")
        self.assertEqual(document.contract_key_canon, "PW-2024-BOE")
        self.assertEqual(document.source_record_id, "BOE-B-2024-12345")
        self.assertEqual(document.metadata["source_url"], url)
        self.assertIn("Adjudicacion del contrato", document.text)
        self.assertTrue((temp / "BOE-B-2024-12345.html").exists())
        self.assertEqual(report["source_registry_id"], "boe_html_individual")
        self.assertEqual(mocked.call_args.args[0].full_url, url)

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
        self.assertIn("agent4_scope", payload)
        self.assertIn("document_source_policy", payload)
        self.assertIn("not_implemented_in_mvp", payload)
        self.assertEqual(
            payload["official_source_registry"]["dataset"],
            "agent4_source_registry",
        )
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

    def test_agent4_evaluation_case_metrics_from_state(self) -> None:
        case = Agent4EvalCase(
            case_id="eval-test",
            contract_key_canon="contract-eval",
            question="evidencia contrato",
            expected_document_ids=("doc-a",),
            expected_terms=("evidencia", "ausente"),
            expect_evidence=True,
        )
        state = {
            "retrieved_context": [
                SimpleNamespace(
                    chunk=DocumentChunk(
                        chunk_id="doc-a:0",
                        document_id="doc-a",
                        text="evidencia contractual",
                        chunk_index=0,
                    )
                ),
                SimpleNamespace(
                    chunk=DocumentChunk(
                        chunk_id="doc-b:0",
                        document_id="doc-b",
                        text="texto adicional",
                        chunk_index=0,
                    )
                ),
            ],
            "citations": ["document_id=doc-a; chunk_id=doc-a:0"],
            "warnings": ["warning de prueba"],
        }

        metrics = evaluate_agent4_case_state(case, state)

        self.assertTrue(metrics["has_evidence"])
        self.assertTrue(metrics["expectation_met"])
        self.assertEqual(metrics["precision_at_k"], 0.5)
        self.assertEqual(metrics["expected_document_recall"], 1.0)
        self.assertEqual(metrics["citation_coverage_ratio"], 0.5)
        self.assertEqual(metrics["expected_term_coverage_ratio"], 0.5)
        self.assertEqual(metrics["matching_document_ids"], ["doc-a"])

    def test_run_agent4_evaluation_offline_writes_report(self) -> None:
        output_path = _test_workspace("evaluation") / "agent4_evaluation_report.json"

        report = run_agent4_evaluation(output_path=output_path, retrieval_limit=5)
        payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["dataset"], "agent4_evaluation_report")
        self.assertEqual(report["mode"], "offline")
        self.assertEqual(report["summary"]["cases_count"], 3)
        self.assertEqual(report["summary"]["cases_with_evidence"], 2)
        self.assertEqual(report["summary"]["expectation_accuracy"], 1.0)
        self.assertEqual(report["summary"]["average_precision_at_k"], 1.0)
        self.assertEqual(report["summary"]["average_expected_document_recall"], 1.0)
        self.assertEqual(payload["summary"], report["summary"])
        self.assertEqual(payload["ragas"]["status"], "not_run")
        self.assertIn("agent4_scope", payload)
        self.assertIn("document_source_policy", payload)
        self.assertIn("not_implemented_in_mvp", payload)

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

    def test_qdrant_existing_collection_with_matching_vector_size_upserts(self) -> None:
        fake_client = _FakeSizedQdrantClient(vector_size=2)
        store = QdrantVectorStore(
            url="http://qdrant.test",
            collection_name="procurement_documents",
            client=fake_client,
        )

        report = store.upsert_chunks(
            [_qdrant_test_chunk()],
            [[0.1, 0.2]],
            _qdrant_test_metadata(dimension=2),
        )

        self.assertEqual(report.vector_size, 2)
        self.assertEqual(fake_client.upserted_collection, "procurement_documents")
        self.assertEqual(fake_client.get_collection_calls, 1)

    def test_qdrant_existing_collection_with_mismatched_vector_size_fails_fast(self) -> None:
        fake_client = _FakeSizedQdrantClient(vector_size=16)
        store = QdrantVectorStore(
            url="http://qdrant.test",
            collection_name="procurement_documents",
            client=fake_client,
        )

        with self.assertRaisesRegex(
            ValueError,
            "vector size 16, but current embeddings require 2",
        ):
            store.upsert_chunks(
                [_qdrant_test_chunk()],
                [[0.1, 0.2]],
                _qdrant_test_metadata(dimension=2),
            )

        self.assertEqual(fake_client.upserted_points, [])

    def test_qdrant_new_rest_collection_is_created_with_current_vector_size(self) -> None:
        fake_client = _FakeRestQdrantClient(exists=False)
        store = QdrantVectorStore(
            url="http://qdrant.test",
            collection_name="procurement_documents",
            client=fake_client,
        )

        report = store.upsert_chunks(
            [_qdrant_test_chunk()],
            [[0.1, 0.2]],
            _qdrant_test_metadata(dimension=2),
        )

        self.assertEqual(report.vector_size, 2)
        self.assertEqual(fake_client.created_vector_size, 2)
        self.assertEqual(fake_client.upserted_collection, "procurement_documents")

    def test_qdrant_rest_collection_vector_size_is_validated(self) -> None:
        fake_client = _FakeRestQdrantClient(exists=True, vector_size=16)
        store = QdrantVectorStore(
            url="http://qdrant.test",
            collection_name="procurement_documents",
            client=fake_client,
        )

        with self.assertRaisesRegex(
            ValueError,
            "vector size 16, but current embeddings require 2",
        ):
            store.upsert_chunks(
                [_qdrant_test_chunk()],
                [[0.1, 0.2]],
                _qdrant_test_metadata(dimension=2),
            )

        self.assertEqual(fake_client.upserted_points, [])

    def test_qdrant_indeterminate_collection_vector_size_does_not_block_upsert(self) -> None:
        fake_client = _FakeSizedQdrantClient(
            collection_info={
                "config": {
                    "params": {
                        "vectors": {
                            "distance": "Cosine",
                        }
                    }
                }
            }
        )
        store = QdrantVectorStore(
            url="http://qdrant.test",
            collection_name="procurement_documents",
            client=fake_client,
        )

        report = store.upsert_chunks(
            [_qdrant_test_chunk()],
            [[0.1, 0.2]],
            _qdrant_test_metadata(dimension=2),
        )

        self.assertEqual(report.vector_size, 2)
        self.assertEqual(fake_client.upserted_collection, "procurement_documents")

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

    def test_cli_agent4_source_registry_command(self) -> None:
        output = io.StringIO()
        output_path = _test_workspace("cli-source-registry") / "registry.json"

        with redirect_stdout(output):
            exit_code = main(["agent4-source-registry", "--output", str(output_path)])

        payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["dataset"], "agent4_source_registry")
        self.assertIn("Registro de fuentes Agent4 generado", output.getvalue())

    def test_cli_agent4_fetch_boe_html_command_uses_fetcher_and_writes_report(self) -> None:
        output = io.StringIO()
        temp = _test_workspace("cli-boe-fetch")
        report_output = temp / "fetch_report.json"
        document = DocumentRef(
            document_id="BOE-B-2024-12345-abcdef",
            source="boe_html",
            text="Adjudicacion del contrato",
            contract_key_canon="PW-2024-BOE",
            source_record_id="BOE-B-2024-12345",
            document_type="html",
            text_hash="a" * 64,
            metadata={
                "path": str(temp / "BOE-B-2024-12345.html"),
                "source_registry_id": "boe_html_individual",
                "source_url": "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2024-12345",
                "downloaded_bytes": "128",
                "html_parser": "html.parser",
            },
        )

        with patch("procurewatch.agent4.fetch_boe_html_document", return_value=document) as mocked:
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "agent4-fetch-boe-html",
                        "--url",
                        "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2024-12345",
                        "--contract-key",
                        "PW-2024-BOE",
                        "--output-dir",
                        str(temp),
                        "--report-output",
                        str(report_output),
                    ]
                )

        report = json.loads(report_output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(mocked.call_args.kwargs["contract_key_canon"], "PW-2024-BOE")
        self.assertEqual(mocked.call_args.kwargs["output_dir"], temp)
        self.assertEqual(report["source_registry_id"], "boe_html_individual")
        self.assertIn("Anuncio BOE HTML descargado", output.getvalue())

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

    def test_agent4_case_flow_runs_local_poc_and_persists_output(self) -> None:
        output_path = _test_workspace("case-flow") / "agent4_case_context.json"

        state = run_agent4_case_flow(
            contract_key_canon="PW-2024-0001",
            question="evidencia documental",
            output_path=output_path,
            retrieval_limit=3,
        )
        payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(state["contract_key_canon"], "PW-2024-0001")
        self.assertGreaterEqual(len(state["document_refs"]), 1)
        self.assertGreaterEqual(len(state["chunks"]), 1)
        self.assertGreaterEqual(len(state["retrieved_context"]), 1)
        self.assertGreaterEqual(len(state["citations"]), 1)
        self.assertIn("No se declara fraude", state["answer"])
        self.assertEqual(payload["contract_key_canon"], "PW-2024-0001")
        self.assertTrue(payload["citations"])
        self.assertEqual(state["case_context"]["schema_version"], "agent4_case_context_v1")
        self.assertTrue(state["case_context"]["evidences"])
        self.assertIn("agent4_scope", state["case_context"])
        self.assertIn("document_source_policy", state["case_context"])
        self.assertIn("not_implemented_in_mvp", state["case_context"])
        self.assertEqual(
            state["case_context"]["contract_fields_used"]["contract_key_canon"],
            "PW-2024-0001",
        )
        self.assertIn("contract_key_canon=PW-2024-0001", state["citations"][0])
        self.assertEqual(payload["case_context"]["schema_version"], "agent4_case_context_v1")

    def test_agent4_case_flow_without_evidence_keeps_warning_and_empty_context(self) -> None:
        output_path = _test_workspace("case-flow-empty") / "agent4_case_context.json"

        state = run_agent4_case_flow(
            contract_key_canon="PW-2024-0001",
            question="termino-inexistente",
            output_path=output_path,
            retrieval_limit=3,
        )
        payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(state["case_context"]["evidences"], [])
        self.assertEqual(state["case_context"]["citations"], [])
        self.assertIn("No hay evidencia documental suficiente", state["case_context"]["summary"])
        self.assertIn(
            "No hay evidencia documental recuperada para responder con trazabilidad.",
            state["warnings"],
        )
        self.assertEqual(payload["case_context"]["evidences"], [])

    def test_agent4_case_context_keeps_contract_fields_and_agent3_metrics(self) -> None:
        state = run_agent4_graph(
            {
                "run_id": "run-metrics",
                "contract_key_canon": "PW-2024-METRICS",
                "question": "evidencia tecnica",
                "document_refs": [
                    DocumentRef(
                        document_id="doc-metrics",
                        source="synthetic",
                        text="La evidencia tecnica confirma trazabilidad documental.",
                        contract_key_canon="PW-2024-METRICS",
                        source_record_id="SYN-METRICS",
                    )
                ],
                "contract_context": {
                    "contract_key_canon": "PW-2024-METRICS",
                    "estimated_value": 125000,
                    "empty_field": "",
                },
                "agent3_metrics": {
                    "supplier_degree": 2,
                    "empty_metric": None,
                },
            }
        )

        case_context = state["case_context"]

        self.assertEqual(case_context["contract_fields_used"]["estimated_value"], 125000)
        self.assertNotIn("empty_field", case_context["contract_fields_used"])
        self.assertEqual(case_context["agent3_metrics_used"]["supplier_degree"], 2)
        self.assertNotIn("empty_metric", case_context["agent3_metrics_used"])

    def test_agent4_case_context_keeps_agent2_score(self) -> None:
        state = run_agent4_graph(
            {
                "run_id": "run-agent2",
                "contract_key_canon": "PW-2024-AGENT2",
                "question": "evidencia documental",
                "document_refs": [
                    DocumentRef(
                        document_id="doc-agent2",
                        source="synthetic",
                        text="La evidencia documental esta disponible.",
                        contract_key_canon="PW-2024-AGENT2",
                    )
                ],
                "agent2_score": {
                    "contract_key_canon": "PW-2024-AGENT2",
                    "risk_score": 0.25,
                    "red_flags": ["missing_supplier"],
                    "evidence": {},
                },
            }
        )

        case_context = state["case_context"]

        self.assertEqual(case_context["agent2_score"]["risk_score"], 0.25)
        self.assertEqual(case_context["agent2_score"]["red_flags"], ["missing_supplier"])

    def test_agent4_case_context_integrates_agent2_agent3_and_persists_output(self) -> None:
        import pandas as pd

        temp = _test_workspace("case-context-integrated")
        canonical_path = temp / "canonical.parquet"
        agent3_features_path = temp / "agent3_features.parquet"
        output_path = temp / "case_context.json"
        pd.DataFrame(
            [
                {
                    "contract_key_canon": "PW-2024-0001",
                    "source": "boe",
                    "source_record_id": "BOE-1",
                    "source_dataset": "boe_2014_2024",
                    "buyer_name": "Ayuntamiento Alfa",
                    "buyer_id": "B1",
                    "supplier_name": "",
                    "supplier_id": "",
                    "contract_title": "Servicios de ingenieria",
                    "procedure": "abierto",
                    "publication_date": "2024-01-10",
                    "award_date": "2024-02-10",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 125.0,
                    "cpv_codes_raw": "71000000-8",
                    "cpv_code_list": "71000000",
                    "source_file": "boe.csv",
                }
            ]
        ).to_parquet(canonical_path, index=False)
        pd.DataFrame(
            [
                {
                    "contract_key_canon": "PW-2024-0001",
                    "buyer_supplier_recurrence": 4,
                    "supplier_degree": 3,
                    "contract_neighbor_count": 5,
                    "has_supplier": False,
                }
            ]
        ).to_parquet(agent3_features_path, index=False)

        state = run_agent4_case_context(
            contract_key_canon="PW-2024-0001",
            question="evidencia documental",
            canonical_path=canonical_path,
            agent3_features_path=agent3_features_path,
            output_path=output_path,
            retrieval_limit=3,
        )
        payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(state["agent2_score"]["risk_score"], 0.5)
        self.assertEqual(
            state["agent2_score"]["red_flags"],
            ["missing_supplier", "awarded_above_estimate"],
        )
        self.assertEqual(state["agent3_metrics"]["supplier_degree"], 3)
        self.assertGreaterEqual(len(state["retrieved_context"]), 1)
        self.assertEqual(payload["agent2_score"]["risk_score"], 0.5)
        self.assertEqual(payload["case_context"]["agent2_score"]["risk_score"], 0.5)
        self.assertEqual(
            payload["case_context"]["contract_fields_used"]["buyer_name"],
            "Ayuntamiento Alfa",
        )
        self.assertEqual(payload["case_context"]["agent3_metrics_used"]["supplier_degree"], 3)
        self.assertTrue(payload["case_context"]["evidences"])

    def test_agent4_case_context_warns_and_continues_without_agent3_metrics(self) -> None:
        import pandas as pd

        temp = _test_workspace("case-context-no-agent3")
        canonical_path = temp / "canonical.parquet"
        output_path = temp / "case_context.json"
        pd.DataFrame(
            [
                {
                    "contract_key_canon": "PW-2024-0001",
                    "source": "boe",
                    "supplier_name": "Proveedor Uno",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 90.0,
                }
            ]
        ).to_parquet(canonical_path, index=False)

        state = run_agent4_case_context(
            contract_key_canon="PW-2024-0001",
            question="evidencia documental",
            canonical_path=canonical_path,
            agent3_features_path=temp / "missing_agent3.parquet",
            output_path=output_path,
        )

        self.assertIsNone(state.get("agent3_metrics"))
        self.assertEqual(state["agent2_score"]["risk_score"], 0.0)
        self.assertIn("Se continua sin metricas relacionales", " ".join(state["warnings"]))

    def test_agent4_case_context_raises_for_missing_contract(self) -> None:
        import pandas as pd

        temp = _test_workspace("case-context-missing-contract")
        canonical_path = temp / "canonical.parquet"
        pd.DataFrame(
            [
                {
                    "contract_key_canon": "PW-2024-0001",
                    "source": "boe",
                }
            ]
        ).to_parquet(canonical_path, index=False)

        with self.assertRaisesRegex(ValueError, "No se encuentra PW-2024-MISSING"):
            run_agent4_case_context(
                contract_key_canon="PW-2024-MISSING",
                canonical_path=canonical_path,
                agent3_features_path=temp / "missing_agent3.parquet",
            )

    def test_agent4_case_context_uses_generation_client_when_evidence_exists(self) -> None:
        generation_client = _FakeGenerationClient()

        state = run_agent4_graph(
            {
                "run_id": "run-llm",
                "contract_key_canon": "PW-2024-LLM",
                "question": "evidencia documental",
                "document_refs": [
                    DocumentRef(
                        document_id="doc-llm",
                        source="synthetic",
                        text="La evidencia documental contiene trazabilidad para revision.",
                        contract_key_canon="PW-2024-LLM",
                    )
                ],
                "generation_client": generation_client,
            }
        )

        case_context = state["case_context"]

        self.assertEqual(generation_client.calls, 1)
        self.assertEqual(case_context["generation"]["mode"], "ollama")
        self.assertEqual(case_context["generation"]["llm_model"], "fake-llm")
        self.assertIn("Resumen generado por LLM", state["answer"])
        self.assertIn("No se declara fraude", state["answer"])
        self.assertIn("doc-llm", generation_client.prompts[0])

    def test_agent4_case_context_falls_back_when_generation_fails(self) -> None:
        state = run_agent4_graph(
            {
                "run_id": "run-llm-fail",
                "contract_key_canon": "PW-2024-LLM-FAIL",
                "question": "evidencia documental",
                "document_refs": [
                    DocumentRef(
                        document_id="doc-llm-fail",
                        source="synthetic",
                        text="La evidencia documental contiene trazabilidad para revision.",
                        contract_key_canon="PW-2024-LLM-FAIL",
                    )
                ],
                "generation_client": _FailingGenerationClient(),
            }
        )

        self.assertEqual(
            state["case_context"]["generation"]["mode"],
            "deterministic_fallback",
        )
        self.assertIn("No se pudo generar ficha con Ollama", " ".join(state["warnings"]))
        self.assertIn("No se declara fraude", state["answer"])

    def test_agent4_vector_flow_uses_embedding_fallback_and_contract_filter(self) -> None:
        vector_store = _FakeVectorStore()

        state = run_agent4_graph(
            {
                "run_id": "run-vector-fallback",
                "contract_key_canon": "PW-2024-VECTOR",
                "question": "evidencia documental",
                "document_refs": [
                    DocumentRef(
                        document_id="doc-vector",
                        source="synthetic",
                        text="La evidencia documental contiene trazabilidad para revision.",
                        contract_key_canon="PW-2024-VECTOR",
                    )
                ],
                "embedding_client": _FailingEmbeddingClient(),
                "embedding_fallback_client": DeterministicEmbeddingClient(dimension=8),
                "vector_store": vector_store,
            }
        )

        self.assertEqual(state["embedding_metadata"]["embedding_provider"], "deterministic")
        self.assertEqual(state["vector_upsert_report"]["collection_name"], "fake_collection")
        self.assertGreaterEqual(len(state["retrieved_context"]), 1)
        self.assertEqual(vector_store.search_filters.contract_key_canon, "PW-2024-VECTOR")
        self.assertIn(
            "Se usara embedding determinista local para Qdrant",
            " ".join(state["warnings"]),
        )

    def test_cli_agent4_run_flow_command_uses_case_flow(self) -> None:
        output = io.StringIO()
        state = {
            "run_id": "run-test",
            "contract_key_canon": "PW-2024-0001",
            "document_refs": [DocumentRef(document_id="doc", source="test", text="texto")],
            "chunks": [
                DocumentChunk(
                    chunk_id="doc:0",
                    document_id="doc",
                    text="texto",
                    chunk_index=0,
                )
            ],
            "retrieved_context": [],
            "citations": [],
        }

        with patch("procurewatch.agent4.run_agent4_case_flow", return_value=state) as mocked:
            with redirect_stdout(output):
                exit_code = main(["agent4-run-flow", "--contract-key", "PW-2024-0001"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Flujo documental Agent4 ejecutado", output.getvalue())
        self.assertEqual(mocked.call_args.kwargs["contract_key_canon"], "PW-2024-0001")

    def test_cli_agent4_case_context_command_uses_integrated_flow(self) -> None:
        output = io.StringIO()
        state = {
            "run_id": "run-integrated",
            "contract_key_canon": "PW-2024-0001",
            "agent2_score": {
                "contract_key_canon": "PW-2024-0001",
                "risk_score": 0.25,
                "red_flags": ["missing_supplier"],
                "evidence": {},
            },
            "agent3_metrics": {"supplier_degree": 2},
            "retrieved_context": [],
            "citations": [],
            "warnings": [],
        }

        with patch("procurewatch.agent4.run_agent4_case_context", return_value=state) as mocked:
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "agent4-case-context",
                        "--contract-key",
                        "PW-2024-0001",
                        "--canonical-path",
                        "data/processed_sample/agent2_contracts_canonical.parquet",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("Ficha integrada Agent4 ejecutada", output.getvalue())
        self.assertEqual(mocked.call_args.kwargs["contract_key_canon"], "PW-2024-0001")
        self.assertEqual(
            mocked.call_args.kwargs["canonical_path"],
            Path("data/processed_sample/agent2_contracts_canonical.parquet"),
        )

    def test_cli_agent4_evaluate_command_uses_evaluation_flow(self) -> None:
        output = io.StringIO()
        report = {
            "mode": "offline",
            "summary": {
                "cases_count": 3,
                "cases_with_evidence": 2,
                "expectation_accuracy": 1.0,
                "average_precision_at_k": 1.0,
                "average_expected_document_recall": 1.0,
                "average_citation_coverage": 1.0,
                "warnings_count": 1,
            },
        }

        with patch("procurewatch.agent4.run_agent4_evaluation", return_value=report) as mocked:
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "agent4-evaluate",
                        "--eval-set",
                        "data/synthetic/agent4_corpus/agent4_eval_set.json",
                        "--output",
                        "data/processed/agent4_evaluation_report.json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("Evaluacion Agent4 completada", output.getvalue())
        self.assertEqual(
            mocked.call_args.kwargs["eval_set_path"],
            Path("data/synthetic/agent4_corpus/agent4_eval_set.json"),
        )


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


class _FakeHttpHeaders:
    def get_content_charset(self) -> str:
        return "utf-8"


class _FakeHttpResponse:
    headers = _FakeHttpHeaders()

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return (
            b"<html><body><h1>Anuncio BOE-B</h1>"
            b"<p>Adjudicacion del contrato con evidencia documental.</p>"
            b"<script>ignored()</script></body></html>"
        )


def _qdrant_test_chunk() -> DocumentChunk:
    return DocumentChunk(
        chunk_id="doc-sized:0",
        document_id="doc-sized",
        text="evidencia documental",
        chunk_index=0,
        contract_key_canon="contract-sized",
        source="synthetic",
        document_type="text",
    )


def _qdrant_test_metadata(*, dimension: int) -> EmbeddingMetadata:
    return EmbeddingMetadata(
        provider="deterministic",
        model="test-model",
        dimension=dimension,
        indexed_at="2026-06-23T00:00:00+00:00",
    )


class _FakeSizedQdrantClient:
    def __init__(
        self,
        *,
        vector_size: int | None = None,
        collection_info: object | None = None,
    ) -> None:
        self.vector_size = vector_size
        self.collection_info = collection_info
        self.get_collection_calls = 0
        self.upserted_collection = None
        self.upserted_points = []

    def collection_exists(self, *, collection_name: str) -> bool:
        return True

    def get_collection(self, *, collection_name: str) -> object:
        self.get_collection_calls += 1
        if self.collection_info is not None:
            return self.collection_info
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors=SimpleNamespace(size=self.vector_size),
                )
            )
        )

    def upsert(self, *, collection_name: str, points: list[dict[str, object]]) -> None:
        self.upserted_collection = collection_name
        self.upserted_points = points


class _FakeRestQdrantClient(_RestQdrantClient):
    def __init__(self, *, exists: bool, vector_size: int | None = None) -> None:
        self.exists = exists
        self.vector_size = vector_size
        self.created_vector_size = None
        self.upserted_collection = None
        self.upserted_points = []

    def collection_exists(self, *, collection_name: str) -> bool:
        return self.exists

    def get_collection(self, *, collection_name: str) -> dict[str, object]:
        return {
            "result": {
                "config": {
                    "params": {
                        "vectors": {
                            "size": self.vector_size,
                            "distance": "Cosine",
                        }
                    }
                }
            }
        }

    def create_collection(self, *, collection_name: str, vector_size: int) -> None:
        self.exists = True
        self.vector_size = vector_size
        self.created_vector_size = vector_size

    def upsert(self, *, collection_name: str, points: list[dict[str, object]]) -> None:
        self.upserted_collection = collection_name
        self.upserted_points = points


class _FakeGenerationClient:
    provider = "ollama"
    model = "fake-llm"

    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> GenerationResult:
        self.calls += 1
        self.prompts.append(prompt)
        return GenerationResult(
            text="Resumen generado por LLM con citas documentales.",
            provider=self.provider,
            model=self.model,
        )


class _FailingGenerationClient:
    def generate(self, _prompt: str) -> GenerationResult:
        raise RuntimeError("ollama unavailable")


class _FailingEmbeddingClient:
    def embed_texts(self, _texts: list[str]) -> object:
        raise RuntimeError("embedding model unavailable")

    def embed_query(self, _query: str) -> object:
        raise RuntimeError("embedding model unavailable")


class _FakeVectorStore:
    def __init__(self) -> None:
        self.chunks: list[DocumentChunk] = []
        self.search_filters: QdrantSearchFilters | None = None

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        _embedding_metadata: EmbeddingMetadata,
    ) -> object:
        self.chunks = chunks
        return SimpleNamespace(
            collection_name="fake_collection",
            points_count=len(chunks),
            vector_size=len(vectors[0]) if vectors else 0,
        )

    def search(
        self,
        _query_vector: list[float],
        *,
        limit: int,
        filters: QdrantSearchFilters | None = None,
    ) -> list[object]:
        self.search_filters = filters
        return [
            type(
                "Result",
                (),
                {
                    "chunk": chunk,
                    "score": 0.9,
                },
            )()
            for chunk in self.chunks[:limit]
        ]


if __name__ == "__main__":
    unittest.main()
