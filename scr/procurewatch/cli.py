from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from pathlib import Path

from .settings import Settings


def doctor() -> int:
    settings = Settings.from_env()

    print(settings.project_name)
    print(f"Entorno: {settings.environment}")
    print(f"Python: {platform.python_version()}")
    print()

    python_ok = sys.version_info >= (3, 11)
    print(f"[{'OK' if python_ok else 'ERROR'}] Python >= 3.11")

    directories_ok = True
    for directory in settings.required_local_directories():
        exists = directory.exists()
        directories_ok = directories_ok and exists
        print(f"[{'OK' if exists else 'ERROR'}] Carpeta local: {directory}")

    print()
    print("Servicios opcionales:")
    for name, configured in settings.optional_service_status().items():
        status = "configurado" if configured else "pendiente"
        print(f"- {name}: {status}")

    return 0 if python_ok and directories_ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="procurewatch",
        description="Herramientas de desarrollo de ProcureWatch Analytics.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Comprueba el entorno local basico.")
    agent4_source_registry_parser = subparsers.add_parser(
        "agent4-source-registry",
        help="Genera el registro trazable de fuentes oficiales y alcance MVP de Agent4.",
    )
    agent4_source_registry_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/agent4_source_registry.json"),
    )
    agent4_fetch_boe_parser = subparsers.add_parser(
        "agent4-fetch-boe-html",
        help="Descarga un anuncio BOE-B HTML concreto para incorporarlo al corpus documental.",
    )
    agent4_fetch_boe_parser.add_argument("--url", required=True)
    agent4_fetch_boe_parser.add_argument("--contract-key", required=True)
    agent4_fetch_boe_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/agent4/boe_html"),
    )
    agent4_fetch_boe_parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("data/processed/agent4_boe_html_fetch_report.json"),
    )
    agent4_fetch_boe_parser.add_argument("--timeout", type=float, default=30.0)
    agent4_smoke_parser = subparsers.add_parser(
        "agent4-smoke",
        help="Comprueba scaffold local de Agent4 y, opcionalmente, servicios RAG.",
    )
    agent4_smoke_parser.add_argument(
        "--check-services",
        action="store_true",
        help="Comprueba Qdrant y Ollama en los endpoints configurados o localhost.",
    )
    agent4_manifest_parser = subparsers.add_parser(
        "agent4-build-manifest",
        help="Carga el corpus documental de Agent4 y genera su manifiesto.",
    )
    agent4_manifest_parser.add_argument(
        "--corpus-index",
        type=Path,
        default=Path("data/synthetic/agent4_corpus/agent4_corpus_index.json"),
    )
    agent4_manifest_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/agent4_documents_manifest.json"),
    )
    agent4_index_parser = subparsers.add_parser(
        "agent4-index-corpus",
        help="Indexa el corpus documental de Agent4 en Qdrant y permite una busqueda demo.",
    )
    agent4_index_parser.add_argument(
        "--corpus-index",
        type=Path,
        default=Path("data/synthetic/agent4_corpus/agent4_corpus_index.json"),
    )
    agent4_index_parser.add_argument("--qdrant-url", default=None)
    agent4_index_parser.add_argument("--collection", default="procurement_documents")
    agent4_index_parser.add_argument("--ollama-base-url", default=None)
    agent4_index_parser.add_argument("--embedding-model", default=None)
    agent4_index_parser.add_argument("--chunk-size", type=int, default=900)
    agent4_index_parser.add_argument("--overlap", type=int, default=120)
    agent4_index_parser.add_argument("--query", default=None)
    agent4_index_parser.add_argument("--limit", type=int, default=5)
    agent4_index_parser.add_argument("--contract-key", default=None)
    agent4_index_parser.add_argument("--source", default=None)
    agent4_index_parser.add_argument("--document-type", default=None)
    agent4_flow_parser = subparsers.add_parser(
        "agent4-run-flow",
        help="Ejecuta el flujo documental de Agent4 sobre el corpus local.",
    )
    agent4_flow_parser.add_argument("--contract-key", default="PW-2024-0001")
    agent4_flow_parser.add_argument("--question", default="evidencia documental")
    agent4_flow_parser.add_argument(
        "--corpus-index",
        type=Path,
        default=Path("data/synthetic/agent4_corpus/agent4_corpus_index.json"),
    )
    agent4_flow_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/agent4_case_context.json"),
    )
    agent4_flow_parser.add_argument("--chunk-size", type=int, default=900)
    agent4_flow_parser.add_argument("--overlap", type=int, default=120)
    agent4_flow_parser.add_argument("--limit", type=int, default=5)
    agent4_flow_parser.add_argument(
        "--use-services",
        action="store_true",
        help="Usa Qdrant y Ollama configurados en entorno/local para la ficha.",
    )
    agent4_flow_parser.add_argument("--qdrant-url", default=None)
    agent4_flow_parser.add_argument("--collection", default="procurement_documents")
    agent4_flow_parser.add_argument("--ollama-base-url", default=None)
    agent4_flow_parser.add_argument("--embedding-model", default=None)
    agent4_flow_parser.add_argument("--llm-model", default=None)
    agent4_case_context_parser = subparsers.add_parser(
        "agent4-case-context",
        help="Genera ficha integrada Agent4 con contrato canonico, Agent2, Agent3 y RAG.",
    )
    agent4_case_context_parser.add_argument("--contract-key", required=True)
    agent4_case_context_parser.add_argument("--question", default="evidencia documental")
    agent4_case_context_parser.add_argument(
        "--canonical-path",
        type=Path,
        default=Path("data/processed/agent2_contracts_canonical.parquet"),
    )
    agent4_case_context_parser.add_argument(
        "--agent3-features-path",
        type=Path,
        default=Path("data/processed/agent3_agent2_features.parquet"),
    )
    agent4_case_context_parser.add_argument(
        "--corpus-index",
        type=Path,
        default=Path("data/synthetic/agent4_corpus/agent4_corpus_index.json"),
    )
    agent4_case_context_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/agent4_case_context.json"),
    )
    agent4_case_context_parser.add_argument("--chunk-size", type=int, default=900)
    agent4_case_context_parser.add_argument("--overlap", type=int, default=120)
    agent4_case_context_parser.add_argument("--limit", type=int, default=5)
    agent4_case_context_parser.add_argument(
        "--use-services",
        action="store_true",
        help="Usa Qdrant y Ollama configurados en entorno/local para la ficha integrada.",
    )
    agent4_case_context_parser.add_argument("--qdrant-url", default=None)
    agent4_case_context_parser.add_argument("--collection", default="procurement_documents")
    agent4_case_context_parser.add_argument("--ollama-base-url", default=None)
    agent4_case_context_parser.add_argument("--embedding-model", default=None)
    agent4_case_context_parser.add_argument("--llm-model", default=None)
    agent4_evaluate_parser = subparsers.add_parser(
        "agent4-evaluate",
        help="Evalua retrieval, citas y trazabilidad de Agent4 sobre un eval set local.",
    )
    agent4_evaluate_parser.add_argument(
        "--eval-set",
        type=Path,
        default=Path("data/synthetic/agent4_corpus/agent4_eval_set.json"),
    )
    agent4_evaluate_parser.add_argument(
        "--corpus-index",
        type=Path,
        default=Path("data/synthetic/agent4_corpus/agent4_corpus_index.json"),
    )
    agent4_evaluate_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/agent4_evaluation_report.json"),
    )
    agent4_evaluate_parser.add_argument("--chunk-size", type=int, default=900)
    agent4_evaluate_parser.add_argument("--overlap", type=int, default=120)
    agent4_evaluate_parser.add_argument("--limit", type=int, default=5)
    agent4_evaluate_parser.add_argument(
        "--use-services",
        action="store_true",
        help="Evalua usando Qdrant/Ollama configurados; offline por defecto.",
    )
    agent4_evaluate_parser.add_argument("--qdrant-url", default=None)
    agent4_evaluate_parser.add_argument("--collection", default="procurement_documents")
    agent4_evaluate_parser.add_argument("--ollama-base-url", default=None)
    agent4_evaluate_parser.add_argument("--embedding-model", default=None)
    agent4_evaluate_parser.add_argument("--llm-model", default=None)
    sample_parser = subparsers.add_parser(
        "make-agent1-sample",
        help="Genera muestras pequenas de BOE, PLACE y OpenTender para pruebas rapidas.",
    )
    sample_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/synthetic/agent1_sample"),
    )
    sample_parser.add_argument("--rows", type=int, default=1000)
    sample_parser.add_argument("--year", type=int, default=2024)
    sample_parser.add_argument("--cpv-prefix", default="71")
    sample_parser.add_argument(
        "--boe-input",
        type=Path,
        default=Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv"),
    )
    sample_parser.add_argument(
        "--opentender-input",
        type=Path,
        default=Path("data/raw/opentender/data-es-ocds-json.zip"),
    )
    sample_parser.add_argument("--place-inputs", nargs="*", type=Path)
    sample_parser.add_argument("--overwrite", action="store_true")
    normalize_boe_parser = subparsers.add_parser(
        "normalize-boe",
        help="Normaliza el CSV raw BOE y genera datasets processed.",
    )
    normalize_boe_parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv"),
    )
    normalize_boe_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    normalize_boe_parser.add_argument("--limit", type=int, default=None)
    place_parser = subparsers.add_parser(
        "place-sources",
        help="Lista, inspecciona o descarga fuentes oficiales PLACE/Hacienda.",
    )
    place_parser.add_argument("--manifest", type=Path, default=Path("config/place_sources.json"))
    place_parser.add_argument("--year", type=int, default=2024)
    place_parser.add_argument("--datasets", nargs="*", default=None)
    place_parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    place_parser.add_argument("--no-docs", action="store_true")
    place_parser.add_argument("--no-data", action="store_true")
    place_parser.add_argument("--inspect", action="store_true")
    place_parser.add_argument("--download", action="store_true")
    place_parser.add_argument("--overwrite", action="store_true")
    place_parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/raw/place_download_report.json"),
    )
    normalize_place_parser = subparsers.add_parser(
        "normalize-place",
        help="Normaliza ZIPs Atom/XML de PLACE a parquet.",
    )
    normalize_place_parser.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        default=None,
        help="Listado de ZIPs PLACE por procesar.",
    )
    normalize_place_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    normalize_place_parser.add_argument("--cpv-prefix", default="71")
    normalize_place_parser.add_argument("--limit", type=int, default=None)
    normalize_place_parser.add_argument("--progress-every", type=int, default=10000)
    normalize_opentender_parser = subparsers.add_parser(
        "normalize-opentender",
        help="Normaliza descarga OpenTender (OCDS JSON) a parquet.",
    )
    normalize_opentender_parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/opentender/data-es-ocds-json.zip"),
    )
    normalize_opentender_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
    )
    normalize_opentender_parser.add_argument("--year", type=int, default=2024)
    normalize_opentender_parser.add_argument("--cpv-prefix", default="71")
    normalize_opentender_parser.add_argument("--limit", type=int, default=None)
    agent1_parser = subparsers.add_parser(
        "run-agent1",
        help="Ejecuta pipeline del agente 1: BOE + PLACE + OpenTender + cobertura.",
    )
    agent1_parser.add_argument(
        "--boe-input",
        type=Path,
        default=Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv"),
    )
    agent1_parser.add_argument(
        "--opentender-input",
        type=Path,
        default=Path("data/raw/opentender/data-es-ocds-json.zip"),
    )
    agent1_parser.add_argument("--place-inputs", nargs="*", type=Path)
    agent1_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    agent1_parser.add_argument("--cpv-prefix", default="71")
    agent1_parser.add_argument("--year", type=int, default=2024)
    agent1_parser.add_argument("--place-download", action="store_true")
    agent1_parser.add_argument("--place-datasets", nargs="*")
    agent1_parser.add_argument("--limit-boe", type=int, default=None)
    agent1_parser.add_argument("--limit-place", type=int, default=None)
    agent1_parser.add_argument("--limit-opentender", type=int, default=None)
    agent1_parser.add_argument("--force-rebuild", action="store_true")
    agent1_parser.add_argument("--cleanup-downloads", action="store_true")
    agent1_parser.add_argument("--postgres-dsn", default=None)
    agent1_parser.add_argument("--write-postgres", action="store_true")
    agent1_report_parser = subparsers.add_parser(
        "report-agent1-coverage",
        help="Genera informe de cobertura y calidad del dataset analitico Agent1.",
    )
    agent1_report_parser.add_argument(
        "--contracts",
        type=Path,
        default=Path("data/processed/contracts_analytical.parquet"),
    )
    agent1_report_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    mvp_parser = subparsers.add_parser(
        "run-mvp",
        help="Ejecuta el flujo MVP Agent1 con salida analitica y PostgreSQL opcional.",
    )
    mvp_parser.add_argument("--year", type=int, default=2024)
    mvp_parser.add_argument("--cpv-prefix", default="71")
    mvp_parser.add_argument("--postgres-dsn", default=None)
    mvp_parser.add_argument(
        "--boe-input",
        type=Path,
        default=Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv"),
    )
    mvp_parser.add_argument(
        "--opentender-input",
        type=Path,
        default=Path("data/raw/opentender/data-es-ocds-json.zip"),
    )
    mvp_parser.add_argument("--place-inputs", nargs="*", type=Path)
    mvp_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    mvp_parser.add_argument("--buyer-catalog", type=Path, default=None)
    mvp_parser.add_argument("--place-download", action="store_true")
    mvp_parser.add_argument("--place-datasets", nargs="*")
    mvp_parser.add_argument("--cleanup-downloads", action="store_true")
    mvp_parser.add_argument("--force-rebuild", action="store_true")
    agent2_parser = subparsers.add_parser(
        "run-agent2",
        help="Ejecuta scoring determinista v1 del agente 2 sobre el canonico.",
    )
    agent2_parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/agent2_contracts_canonical.parquet"),
    )
    agent2_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    agent2_parser.add_argument("--limit", type=int, default=None)
    agent2_parser.add_argument("--source-snapshot-id", default=None)
    agent2_mvp_parser = subparsers.add_parser(
        "run-agent2-mvp",
        help="Ejecuta el MVP RF-01..RF-06 de Agent2 sobre el canonico.",
    )
    agent2_mvp_parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/agent2_contracts_canonical.parquet"),
    )
    agent2_mvp_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    agent2_mvp_parser.add_argument("--deviation-threshold", type=float, default=0.10)
    agent2_mvp_parser.add_argument(
        "--agent3-features-path",
        type=Path,
        default=Path("data/processed/agent3_agent2_features.parquet"),
    )
    agent3_parser = subparsers.add_parser(
        "run-agent3",
        help="Genera nodos, aristas y metricas locales del agente 3 desde el canonico.",
    )
    agent3_parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/agent2_contracts_canonical.parquet"),
    )
    agent3_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    integrated_demo_parser = subparsers.add_parser(
        "run-integrated-demo",
        help="Regenera la demo offline Agent2-Agent3-Agent4 sin servicios externos.",
    )
    integrated_demo_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/agent3_agent4_demo_2026_06_23"),
    )
    integrated_demo_parser.add_argument("--contract-key", default="PW-2024-0001")
    integrated_demo_parser.add_argument(
        "--question",
        default="evidencia documental y riesgos explicables",
    )
    integrated_demo_parser.add_argument(
        "--corpus-index",
        type=Path,
        default=Path("data/synthetic/agent4_corpus/agent4_corpus_index.json"),
    )
    dashboard_validation_parser = subparsers.add_parser(
        "validate-dashboard-demo",
        help="Valida el dashboard Streamlit contra la demo integrada offline.",
    )
    dashboard_validation_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/agent3_agent4_demo_2026_06_23"),
    )
    dashboard_validation_parser.add_argument("--case-context", type=Path, default=None)
    dashboard_validation_parser.add_argument("--report", type=Path, default=None)
    dashboard_validation_parser.add_argument("--contract-key", default="PW-2024-0001")
    dashboard_validation_parser.add_argument(
        "--question",
        default="evidencia documental y riesgos explicables",
    )
    dashboard_validation_parser.add_argument(
        "--corpus-index",
        type=Path,
        default=Path("data/synthetic/agent4_corpus/agent4_corpus_index.json"),
    )
    dashboard_validation_parser.add_argument(
        "--no-regenerate",
        action="store_true",
        help="Valida artefactos existentes sin regenerar primero la demo integrada.",
    )
    agent3_neo4j_parser = subparsers.add_parser(
        "agent3-load-neo4j",
        help="Carga nodos y aristas del agente 3 en Neo4j.",
    )
    agent3_neo4j_parser.add_argument(
        "--nodes",
        type=Path,
        default=Path("data/processed/agent3_nodes.parquet"),
    )
    agent3_neo4j_parser.add_argument(
        "--edges",
        type=Path,
        default=Path("data/processed/agent3_edges.parquet"),
    )
    agent3_neo4j_parser.add_argument("--uri", default=None)
    agent3_neo4j_parser.add_argument("--user", default=None)
    agent3_neo4j_parser.add_argument("--password", default=None)
    agent3_neo4j_parser.add_argument("--database", default=None)
    batch_parser = subparsers.add_parser(
        "run-batch",
        help="Orquesta ingesta semanal o mensual y estado de batch para cadenas futuras.",
    )
    batch_parser.add_argument("--run-mode", default="weekly", choices=["weekly", "monthly"])
    batch_parser.add_argument("--year", type=int, default=2024)
    batch_parser.add_argument("--cpv-prefix", default="71")
    batch_parser.add_argument("--force", action="store_true")
    batch_parser.add_argument("--place-download", action="store_true")
    batch_parser.add_argument("--place-datasets", nargs="*", default=None)
    batch_parser.add_argument("--no-datos-gob", action="store_true")
    batch_parser.add_argument(
        "--boe-input",
        type=Path,
        default=Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv"),
    )
    batch_parser.add_argument(
        "--opentender-input",
        type=Path,
        default=Path("data/raw/opentender/data-es-ocds-json.zip"),
    )
    batch_parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    batch_parser.add_argument(
        "--manifest-path",
        type=Path,
        default=Path("config/place_sources.json"),
    )
    batch_parser.add_argument(
        "--batch-state-path",
        type=Path,
        default=Path("data/processed/run_batch_state.json"),
    )
    batch_parser.add_argument(
        "--batch-manifest-dir",
        type=Path,
        default=Path("data/manifest/batches"),
    )
    batch_parser.add_argument("--datos-gob-dir", type=Path, default=Path("data/raw/datos_gob"))
    batch_parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    batch_parser.add_argument("--cleanup-downloads", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "agent4-source-registry":
        from .agent4 import write_agent4_source_registry

        registry = write_agent4_source_registry(args.output)
        print("Registro de fuentes Agent4 generado")
        print(f"- Fuentes: {registry['source_count']}")
        print(f"- Output: {args.output}")
        return 0
    if args.command == "agent4-fetch-boe-html":
        from .agent4 import build_boe_html_fetch_report, fetch_boe_html_document

        document = fetch_boe_html_document(
            url=args.url,
            contract_key_canon=args.contract_key,
            output_dir=args.output_dir,
            timeout=args.timeout,
        )
        report = build_boe_html_fetch_report(document)
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("Anuncio BOE HTML descargado para Agent4")
        print(f"- BOE id: {document.source_record_id}")
        print(f"- Contrato: {document.contract_key_canon}")
        print(f"- Documento: {document.document_id}")
        print(f"- HTML local: {document.metadata.get('path')}")
        print(f"- Reporte: {args.report_output}")
        return 0
    if args.command == "agent4-smoke":
        from .agent4.smoke import run_agent4_smoke

        return run_agent4_smoke(check_services=args.check_services)
    if args.command == "agent4-build-manifest":
        from .agent4 import load_corpus_documents, write_documents_manifest

        documents = load_corpus_documents(args.corpus_index)
        manifest = write_documents_manifest(
            documents,
            args.output,
            corpus_index_path=args.corpus_index,
        )
        print("Manifiesto Agent4 generado")
        print(f"- Documentos: {manifest['documents_count']}")
        print(f"- Corpus index: {args.corpus_index}")
        print(f"- Output: {args.output}")
        return 0
    if args.command == "agent4-index-corpus":
        from .agent4 import QdrantSearchFilters, index_corpus_to_qdrant

        settings = Settings.from_env()
        report = index_corpus_to_qdrant(
            corpus_index=args.corpus_index,
            qdrant_url=args.qdrant_url or settings.qdrant_url or "http://localhost:6333",
            collection_name=args.collection,
            ollama_base_url=args.ollama_base_url
            or settings.ollama_base_url
            or "http://localhost:11434",
            embedding_model=args.embedding_model or settings.ollama_embedding_model,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            query=args.query,
            limit=args.limit,
            filters=QdrantSearchFilters(
                contract_key_canon=args.contract_key,
                source=args.source,
                document_type=args.document_type,
            ),
        )
        print("Corpus Agent4 indexado en Qdrant")
        print(f"- Coleccion: {report.collection_name}")
        print(f"- Documentos: {report.documents_count}")
        print(f"- Chunks/puntos: {report.chunks_count}/{report.points_count}")
        print(
            f"- Embeddings: {report.embedding_provider}:{report.embedding_model} "
            f"dim={report.embedding_dimension}"
        )
        if args.query:
            print(f"- Resultados query: {len(report.results)}")
            for result in report.results:
                print(
                    f"  - {result.chunk.chunk_id} "
                    f"score={result.score:.4f} contract={result.chunk.contract_key_canon}"
                )
        return 0
    if args.command == "agent4-run-flow":
        from .agent4 import run_agent4_case_flow

        state = run_agent4_case_flow(
            contract_key_canon=args.contract_key,
            question=args.question,
            corpus_index=args.corpus_index,
            output_path=args.output,
            use_services=args.use_services,
            qdrant_url=args.qdrant_url,
            collection_name=args.collection,
            ollama_base_url=args.ollama_base_url,
            embedding_model=args.embedding_model,
            llm_model=args.llm_model,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            retrieval_limit=args.limit,
        )
        print("Flujo documental Agent4 ejecutado")
        print(f"- Run ID: {state.get('run_id')}")
        print(f"- Contrato: {state.get('contract_key_canon')}")
        print(f"- Documentos: {len(state.get('document_refs', []))}")
        print(f"- Chunks: {len(state.get('chunks', []))}")
        print(f"- Evidencias: {len(state.get('retrieved_context', []))}")
        print(f"- Citas: {len(state.get('citations', []))}")
        case_context = state.get("case_context", {})
        generation = case_context.get("generation", {}) if isinstance(case_context, dict) else {}
        if generation:
            print(f"- Generacion: {generation.get('mode')}")
        vector_report = state.get("vector_upsert_report", {})
        if vector_report:
            print(f"- Vector store: {vector_report.get('collection_name')}")
        print(f"- Output: {args.output}")
        return 0
    if args.command == "agent4-case-context":
        from .agent4 import run_agent4_case_context

        state = run_agent4_case_context(
            contract_key_canon=args.contract_key,
            question=args.question,
            canonical_path=args.canonical_path,
            agent3_features_path=args.agent3_features_path,
            corpus_index=args.corpus_index,
            output_path=args.output,
            use_services=args.use_services,
            qdrant_url=args.qdrant_url,
            collection_name=args.collection,
            ollama_base_url=args.ollama_base_url,
            embedding_model=args.embedding_model,
            llm_model=args.llm_model,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            retrieval_limit=args.limit,
        )
        agent2_score = state.get("agent2_score", {})
        red_flags = agent2_score.get("red_flags", []) if isinstance(agent2_score, dict) else []
        agent3_metrics = state.get("agent3_metrics", {})
        print("Ficha integrada Agent4 ejecutada")
        print(f"- Run ID: {state.get('run_id')}")
        print(f"- Contrato: {state.get('contract_key_canon')}")
        if isinstance(agent2_score, dict):
            print(f"- Agent2 risk_score: {agent2_score.get('risk_score')}")
        print(f"- Agent2 red flags: {len(red_flags) if isinstance(red_flags, list) else 0}")
        print(f"- Agent3 metricas: {'si' if agent3_metrics else 'no'}")
        print(f"- Evidencias: {len(state.get('retrieved_context', []))}")
        print(f"- Citas: {len(state.get('citations', []))}")
        print(f"- Warnings: {len(state.get('warnings', []))}")
        print(f"- Output: {args.output}")
        return 0
    if args.command == "agent4-evaluate":
        from .agent4 import run_agent4_evaluation

        report = run_agent4_evaluation(
            eval_set_path=args.eval_set,
            corpus_index=args.corpus_index,
            output_path=args.output,
            use_services=args.use_services,
            qdrant_url=args.qdrant_url,
            collection_name=args.collection,
            ollama_base_url=args.ollama_base_url,
            embedding_model=args.embedding_model,
            llm_model=args.llm_model,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            retrieval_limit=args.limit,
        )
        summary = report["summary"]
        print("Evaluacion Agent4 completada")
        print(f"- Modo: {report['mode']}")
        print(f"- Casos: {summary['cases_count']}")
        print(f"- Casos con evidencia: {summary['cases_with_evidence']}")
        print(f"- Accuracy expectativas: {summary['expectation_accuracy']}")
        print(f"- Precision@k media: {summary['average_precision_at_k']}")
        print(f"- Recall documentos esperado: {summary['average_expected_document_recall']}")
        print(f"- Cobertura citas media: {summary['average_citation_coverage']}")
        print(f"- Warnings: {summary['warnings_count']}")
        print(f"- Output: {args.output}")
        return 0
    if args.command == "make-agent1-sample":
        from .samples import make_agent1_sample

        report = make_agent1_sample(
            output_dir=args.output_dir,
            rows=args.rows,
            year=args.year,
            cpv_prefix=args.cpv_prefix,
            boe_input=args.boe_input,
            opentender_input=args.opentender_input,
            place_inputs=args.place_inputs or None,
            overwrite=args.overwrite,
        )
        print("Muestras Agent1 generadas")
        print(f"- Directorio: {report['output_dir']}")
        print(f"- Manifest: {args.output_dir / 'sample_manifest.json'}")
        print(f"- Comando recomendado: {report['agent1_command']}")
        return 0
    if args.command == "normalize-boe":
        from .data_sources.boe import normalize_boe_file

        boe_report = normalize_boe_file(args.input, args.output_dir, limit=args.limit)
        rows = boe_report["rows"]
        print("Normalizacion BOE completada")
        print(f"- Filas parseadas: {rows['parsed_rows']} / {rows['total_data_lines']}")
        print(f"- Errores de parseo: {rows['parse_errors']}")
        print(f"- Filas CPV 71: {rows['cpv71_rows']}")
        print(f"- Dataset: {boe_report['outputs']['contracts_boe']}")
        print(f"- Dataset CPV 71: {boe_report['outputs']['contracts_boe_cpv71']}")
        print(f"- Reporte: {args.output_dir / 'data_quality_report.json'}")
        return 0
    if args.command == "place-sources":
        from .data_sources.place import (
            build_targets,
            download_targets,
            inspect_targets,
            load_manifest,
            write_report,
        )

        manifest = load_manifest(args.manifest)
        targets = build_targets(
            manifest,
            year=args.year,
            dataset_ids=set(args.datasets) if args.datasets else None,
            include_docs=not args.no_docs,
            include_data=not args.no_data,
            raw_dir=args.raw_dir,
        )
        if not args.inspect and not args.download:
            for target in targets:
                print(f"{target.id}: {target.url} -> {target.output_path}")
            return 0

        place_report = (
            inspect_targets(targets)
            if args.inspect
            else download_targets(
                targets,
                overwrite=args.overwrite,
            )
        )
        write_report(place_report, args.report)
        for item in place_report:
            status = item.get("status_code", "n/a")
            size = item.get("content_length") or item.get("size_bytes") or "unknown"
            marker = "OK" if item.get("available", item.get("downloaded", False)) else "WARN"
            print(f"[{marker}] {item['id']} status={status} size={size} -> {item['output_path']}")
        print(f"Reporte: {args.report}")
        return 0
    if args.command == "normalize-place":
        from .data_sources.place_normalize import normalize_place_archives

        place_paths = args.inputs or [
            Path("data/raw/place/profiles/licitacionesPerfilesContratanteCompleto3_2024.zip"),
            Path("data/raw/place/aggregation/PlataformasAgregadasSinMenores_2024.zip"),
        ]
        place_report = normalize_place_archives(
            place_paths,
            output_dir=args.output_dir,
            cpv_prefix=args.cpv_prefix,
            limit=args.limit,
            progress_every=args.progress_every,
        )
        rows = place_report["rows"]
        print("Normalizacion PLACE completada")
        print(f"- Entradas deduplicadas: {rows['deduped_rows']}")
        print(f"- Entradas CPV71: {rows['cpv71_rows']}")
        print(f"- Output: {place_report['outputs']['contracts_place']}")
        return 0
    if args.command == "normalize-opentender":
        from .data_sources.opentender import normalize_opentender_file

        opentender_report = normalize_opentender_file(
            input_path=args.input,
            output_dir=args.output_dir,
            year=args.year,
            cpv_prefix=args.cpv_prefix,
            limit=args.limit,
        )
        rows = opentender_report["rows"]
        print("Normalizacion OpenTender completada")
        print(f"- Registros parseados: {rows['parsed_records']} / {rows['raw_lines_read']}")
        print(f"- Registros CPV71: {rows['cpv71_rows']}")
        print(f"- Output: {opentender_report['outputs']['contracts_opentender']}")
        return 0
    if args.command == "run-agent1":
        from .agent1 import run_agent1

        if args.place_download:
            place_inputs: list[Path] = list(args.place_inputs) if args.place_inputs else []
        else:
            place_inputs = args.place_inputs or [
                Path("data/raw/place/profiles/licitacionesPerfilesContratanteCompleto3_2024.zip"),
                Path("data/raw/place/aggregation/PlataformasAgregadasSinMenores_2024.zip"),
            ]
        reports = run_agent1(
            boe_input=args.boe_input,
            open_tender_input=args.opentender_input,
            place_inputs=place_inputs,
            output_dir=args.output_dir,
            cpv_prefix=args.cpv_prefix,
            year=args.year,
            place_download=args.place_download,
            place_datasets=args.place_datasets,
            limit_boe=args.limit_boe,
            limit_place=args.limit_place,
            limit_ot=args.limit_opentender,
            force_rebuild=args.force_rebuild,
            cleanup_downloads=args.cleanup_downloads,
            postgres_dsn=args.postgres_dsn,
            write_postgres=args.write_postgres,
        )

        print("Agente 1 ejecutado")
        print(f"- Cobertura BOE/PLACE/OpenTender: {reports['coverage']}")
        print(f"- Entrega: {args.output_dir}")
        print(f"- Reporte agente: {reports['agent1_run_report_path']}")
        return 0
    if args.command == "run-mvp":
        from .agent1 import run_agent1

        settings = Settings.from_env()
        postgres_dsn = args.postgres_dsn or settings.postgres_dsn
        if args.place_download:
            place_inputs = list(args.place_inputs) if args.place_inputs else []
        else:
            place_inputs = args.place_inputs or [
                Path("data/raw/place/profiles/licitacionesPerfilesContratanteCompleto3_2024.zip"),
                Path("data/raw/place/aggregation/PlataformasAgregadasSinMenores_2024.zip"),
            ]
        reports = run_agent1(
            boe_input=args.boe_input,
            open_tender_input=args.opentender_input,
            place_inputs=place_inputs,
            output_dir=args.output_dir,
            cpv_prefix=args.cpv_prefix,
            year=args.year,
            place_download=args.place_download,
            place_datasets=args.place_datasets,
            buyer_catalog_path=args.buyer_catalog,
            cleanup_downloads=args.cleanup_downloads,
            force_rebuild=args.force_rebuild,
            postgres_dsn=postgres_dsn,
            write_postgres=postgres_dsn is not None,
        )
        print("MVP ejecutado")
        print(f"- PostgreSQL: {'si' if postgres_dsn else 'no'}")
        print(f"- Reporte agente: {reports['agent1_run_report_path']}")
        return 0
    if args.command == "report-agent1-coverage":
        from .agent1 import build_agent1_coverage_report

        report = build_agent1_coverage_report(
            contracts_path=args.contracts,
            output_dir=args.output_dir,
        )
        print("Informe Agent1 generado")
        print(f"- Estado global: {report['overall_status']}")
        print(f"- Output JSON: {report['outputs']['json']}")
        return 0
    if args.command == "run-agent2":
        from .agent2 import run_agent2

        report = run_agent2(
            input_path=args.input,
            output_dir=args.output_dir,
            limit=args.limit,
            source_snapshot_id=args.source_snapshot_id,
        )
        print("Agente 2 ejecutado")
        print(f"- Contratos evaluados: {report['input_rows']}")
        print(f"- Scores: {report['scores_rows']}")
        print(f"- Flags: {report['flags_rows']}")
        print(f"- Niveles riesgo: {report['risk_level_counts']}")
        print(f"- Reporte agente: {report['outputs']['report']}")
        return 0
    if args.command == "run-agent2-mvp":
        from .agent2 import run_agent2_mvp

        report = run_agent2_mvp(
            input_path=args.input,
            output_dir=args.output_dir,
            deviation_threshold=args.deviation_threshold,
            agent3_features_path=args.agent3_features_path,
        )
        print("Agente 2 MVP ejecutado")
        print(f"- Contratos evaluados: {report['rows']}")
        print(f"- Contratos con flags: {report['activated_contract_rows']}")
        print(f"- Flags activadas: {report['activated_flags']}")
        print(f"- Reporte agente: {report['report_path']}")
        return 0
    if args.command == "run-agent3":
        from .agent3 import run_agent3

        report = run_agent3(input_path=args.input, output_dir=args.output_dir)
        print("Agente 3 ejecutado")
        print(f"- Nodos: {report['nodes_rows']}")
        print(f"- Aristas: {report['edges_rows']}")
        print(f"- Metricas contrato: {report['contract_metrics_rows']}")
        print(f"- Features Agent2: {report['agent2_features_rows']}")
        print(f"- Reporte agente: {report['outputs']['report']}")
        return 0
    if args.command == "run-integrated-demo":
        from .integrated_demo import run_integrated_demo

        report = run_integrated_demo(
            output_dir=args.output_dir,
            contract_key_canon=args.contract_key,
            question=args.question,
            corpus_index=args.corpus_index,
        )
        summary = report["summary"]
        print(f"Demo integrada Agent2-Agent3-Agent4 [{report['status']}]")
        print(f"- Contrato: {report['contract_key_canon']}")
        print(f"- Canonico demo: {report['artifacts']['canonical']}")
        print(f"- Agent3 nodos/aristas: {summary['agent3_nodes']}/{summary['agent3_edges']}")
        print(f"- Agent2 risk_score: {summary['agent2_risk_score']}")
        print(f"- Agent2 red flags: {len(summary['agent2_red_flags'])}")
        print(
            f"- Agent4 evidencias/citas: "
            f"{summary['agent4_evidences']}/{summary['agent4_citations']}"
        )
        print(f"- Reporte integrado: {report['artifacts']['integrated_report']}")
        return 0 if report["status"] == "ready" else 1
    if args.command == "validate-dashboard-demo":
        from .dashboard_validation import validate_dashboard_demo

        report = validate_dashboard_demo(
            output_dir=args.output_dir,
            case_context_path=args.case_context,
            report_path=args.report,
            contract_key_canon=args.contract_key,
            question=args.question,
            corpus_index=args.corpus_index,
            regenerate=not args.no_regenerate,
        )
        print(f"Dashboard Streamlit demo [{report['status']}]")
        print(f"- Demo dir: {report['output_dir']}")
        print(f"- Ficha Agent4: {report['case_context_path']}")
        print(f"- Contratos: {report['kpis'].get('contracts', 0)}")
        print(
            f"- Nodos/aristas: "
            f"{report['kpis'].get('nodes', 0)}/{report['kpis'].get('edges', 0)}"
        )
        print(
            f"- Evidencias/citas: "
            f"{report['case_summary']['evidences_count']}/"
            f"{report['case_summary']['citations_count']}"
        )
        print(f"- Headless exceptions: {len(report['streamlit_headless']['exceptions'])}")
        print(f"- Reporte: {report['artifacts']['dashboard_validation_report']}")
        return 0 if report["status"] == "ready" else 1
    if args.command == "agent3-load-neo4j":
        from .agent3.neo4j_store import (
            DEFAULT_NEO4J_PASSWORD,
            DEFAULT_NEO4J_URI,
            DEFAULT_NEO4J_USER,
            load_graph_to_neo4j,
        )

        settings = Settings.from_env()
        uri = args.uri or settings.neo4j_uri or DEFAULT_NEO4J_URI
        user = args.user or settings.neo4j_user or DEFAULT_NEO4J_USER
        password = args.password or settings.neo4j_password or DEFAULT_NEO4J_PASSWORD
        report = load_graph_to_neo4j(
            nodes_path=args.nodes,
            edges_path=args.edges,
            uri=uri,
            user=user,
            password=password,
            database=args.database,
        )
        print("Agente 3 cargado en Neo4j")
        print(f"- URI: {uri}")
        print(f"- Nodos procesados: {report['nodes_processed']}")
        print(f"- Aristas procesadas: {report['edges_processed']}")
        print(f"- Nodos Neo4j por tipo: {report['controls'].get('nodes_by_type', {})}")
        print(f"- Aristas Neo4j por tipo: {report['controls'].get('edges_by_type', {})}")
        return 0
    if args.command == "run-batch":
        from .batch import run_batch

        result = run_batch(
            run_mode=args.run_mode,
            year=args.year,
            cpv_prefix=args.cpv_prefix,
            force=args.force,
            place_download=args.place_download,
            place_datasets=args.place_datasets,
            include_datos_gob=not args.no_datos_gob,
            boe_input=args.boe_input,
            open_tender_input=args.opentender_input,
            processed_dir=args.processed_dir,
            manifest_path=args.manifest_path,
            batch_state_path=args.batch_state_path,
            batch_manifest_dir=args.batch_manifest_dir,
            datos_gob_dir=args.datos_gob_dir,
            raw_dir=args.raw_dir,
            cleanup_downloads=args.cleanup_downloads,
        )

        print(f"run-batch [{result['status']}]")
        print(f"batch_id: {result['batch_id']}")
        print(f"agent1_executed: {result['agent1_executed']}")
        print(f"changed_sources: {result['changed_sources']}")
        print(f"missing_required_inputs: {result['missing_required_inputs']}")
        print(f"manifest: {result['batch_manifest_path']}")
        if result.get("agent1_run_report_path"):
            print(f"agent1_report: {result['agent1_run_report_path']}")
        return 0 if result["status"] in {"executed", "skipped"} else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
