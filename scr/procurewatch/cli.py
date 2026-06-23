from __future__ import annotations

import argparse
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
    agent4_smoke_parser = subparsers.add_parser(
        "agent4-smoke",
        help="Comprueba scaffold local de Agent4 y, opcionalmente, servicios RAG.",
    )
    agent4_smoke_parser.add_argument(
        "--check-services",
        action="store_true",
        help="Comprueba Qdrant y Ollama en los endpoints configurados o localhost.",
    )
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
    agent1_parser.add_argument(
        "--opentender-download-url",
        type=str,
        default=None,
        help="URL de OpenTender para bajar el fichero temporalmente; prioriza la página española y usa fallback técnico si hace falta.",
    )
    agent1_parser.add_argument("--place-inputs", nargs="*", type=Path)
    agent1_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    agent1_parser.add_argument("--cpv-prefix", default="71")
    agent1_parser.add_argument("--year", type=int, default=2024)
    agent1_parser.add_argument("--place-download", action="store_true")
    agent1_parser.add_argument("--place-datasets", nargs="*")
    agent1_parser.add_argument(
        "--buyer-catalog",
        type=Path,
        default=None,
        help="Excel oficial de organos contratantes para enriquecer codigo_organismo y nivel_administracion.",
    )
    agent1_parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directorio donde descargar temporalmente las fuentes brutas.",
    )
    agent1_parser.add_argument(
        "--cleanup-downloads",
        action="store_true",
        help="Borra los archivos descargados por el pipeline al terminar.",
    )
    agent1_parser.add_argument("--limit-boe", type=int, default=None)
    agent1_parser.add_argument("--limit-place", type=int, default=None)
    agent1_parser.add_argument("--limit-opentender", type=int, default=None)
    agent1_parser.add_argument("--force-rebuild", action="store_true")
    agent1_parser.add_argument(
        "--postgres-dsn",
        type=str,
        default=None,
        help="DSN de PostgreSQL para persistir las tablas analíticas mínimas del MVP.",
    )
    agent1_parser.add_argument(
        "--write-postgres",
        action="store_true",
        help="Guarda CONTRACTO y ADJUDICATARIO en PostgreSQL tras generar los Parquet.",
    )
    agent1_report_parser = subparsers.add_parser(
        "report-agent1-coverage",
        help="Genera el informe de cobertura y requisitos pendientes del agente 1.",
    )
    agent1_report_parser.add_argument(
        "--contracts",
        type=Path,
        default=Path("data/processed/contracts_analytical.parquet"),
    )
    agent1_report_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
    )
    mvp_parser = subparsers.add_parser(
        "run-mvp",
        help="Ejecuta el MVP de Agent1 y persiste en PostgreSQL si el DSN está configurado.",
    )
    mvp_parser.add_argument("--year", type=int, default=2024)
    mvp_parser.add_argument("--cpv-prefix", default="71")
    mvp_parser.add_argument(
        "--postgres-dsn",
        type=str,
        default=None,
        help="Sobrescribe el DSN de PostgreSQL del entorno si es necesario.",
    )
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
    mvp_parser.add_argument("--buyer-catalog", type=Path, default=None)
    mvp_parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
    )
    mvp_parser.add_argument("--place-download", action="store_true")
    mvp_parser.add_argument("--place-datasets", nargs="*")
    mvp_parser.add_argument("--cleanup-downloads", action="store_true")
    mvp_parser.add_argument("--force-rebuild", action="store_true")
    mvp_parser.add_argument(
        "--opentender-download-url",
        type=str,
        default=None,
        help="URL de OpenTender para descargar el fichero temporalmente.",
    )
    agent2_parser = subparsers.add_parser(
        "run-agent2",
        help="Ejecuta las red flags y el scoring determinista del agente 2.",
    )
    agent2_parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/agent2_contracts_canonical.parquet"),
    )
    agent2_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    agent2_parser.add_argument(
        "--deviation-threshold",
        type=float,
        default=0.10,
        help="Desviacion relativa minima para activar RF-05 (por defecto: 0.10).",
    )
    agent2_parser.add_argument(
        "--postgres-dsn",
        type=str,
        default=None,
        help="DSN de PostgreSQL para persistir las tablas de riesgo del MVP.",
    )
    agent2_parser.add_argument(
        "--write-postgres",
        action="store_true",
        help="Guarda risk_flags, risk_scores y agent_outputs en PostgreSQL.",
    )
    agent2_mvp_parser = subparsers.add_parser(
        "run-agent2-mvp",
        help="Ejecuta Agent 2 sobre el canonico de Agent 1 con el conjunto minimo de red flags.",
    )
    agent2_mvp_parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/agent2_contracts_canonical.parquet"),
    )
    agent2_mvp_parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    agent2_mvp_parser.add_argument(
        "--deviation-threshold",
        type=float,
        default=0.10,
        help="Desviacion relativa minima para activar RF-05 (por defecto: 0.10).",
    )
    agent2_mvp_parser.add_argument(
        "--postgres-dsn",
        type=str,
        default=None,
        help="Sobrescribe el DSN de PostgreSQL del entorno si es necesario.",
    )
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

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "agent4-smoke":
        from .agent4.smoke import run_agent4_smoke

        return run_agent4_smoke(check_services=args.check_services)
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
            open_tender_download_url=args.opentender_download_url,
            place_inputs=place_inputs,
            output_dir=args.output_dir,
            cpv_prefix=args.cpv_prefix,
            year=args.year,
            place_download=args.place_download,
            place_datasets=args.place_datasets,
            buyer_catalog_path=args.buyer_catalog,
            raw_dir=args.raw_dir,
            cleanup_downloads=args.cleanup_downloads,
            limit_boe=args.limit_boe,
            limit_place=args.limit_place,
            limit_ot=args.limit_opentender,
            force_rebuild=args.force_rebuild,
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
            place_inputs: list[Path] = list(args.place_inputs) if args.place_inputs else []
        else:
            place_inputs = args.place_inputs or [
                Path("data/raw/place/profiles/licitacionesPerfilesContratanteCompleto3_2024.zip"),
                Path("data/raw/place/aggregation/PlataformasAgregadasSinMenores_2024.zip"),
            ]
        reports = run_agent1(
            boe_input=args.boe_input,
            open_tender_input=args.opentender_input,
            open_tender_download_url=args.opentender_download_url,
            place_inputs=place_inputs,
            output_dir=Path("data/processed"),
            cpv_prefix=args.cpv_prefix,
            year=args.year,
            place_download=args.place_download,
            place_datasets=args.place_datasets,
            buyer_catalog_path=args.buyer_catalog,
            raw_dir=args.raw_dir,
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
        metrics = report["quality_metrics"]
        print("Informe de cobertura del Agente 1 generado")
        print(f"- Estado global: {report['overall_status']}")
        print(f"- Contratos analizados: {report['scope']['rows']}")
        print(
            "- Completitud OCDS crítica: "
            f"{metrics['ocds_critical_completeness']['coverage_ratio']:.2%}"
        )
        print(f"- Cobertura NIF: {metrics['supplier_nif_coverage']['coverage_ratio']:.2%}")
        temporal = metrics["temporal_coherence"]["coherence_ratio"]
        temporal_text = "no evaluable" if temporal is None else f"{temporal:.2%}"
        print(f"- Coherencia temporal: {temporal_text}")
        print(f"- Informe: {report['outputs']['markdown']}")
        return 0
    if args.command == "run-agent2":
        from .agent2 import run_agent2

        report = run_agent2(
            input_path=args.input,
            output_dir=args.output_dir,
            deviation_threshold=args.deviation_threshold,
            postgres_dsn=args.postgres_dsn,
            write_postgres=args.write_postgres,
        )
        print("Agente 2 ejecutado")
        print(f"- Contratos de entrada: {report['rows']}")
        print(f"- Contratos evaluables: {report['evaluable_rows']}")
        print(f"- Contratos con alguna señal: {report['activated_contract_rows']}")
        print(f"- Señales activadas: {report['activated_flags']}")
        if report.get("postgres_write"):
            print(f"- PostgreSQL: {report['postgres_write']['postgres_dsn']}")
        print(f"- Reporte: {report['report_path']}")
        return 0
    if args.command == "run-agent2-mvp":
        from .agent2 import run_agent2
        settings = Settings.from_env()
        postgres_dsn = args.postgres_dsn or settings.postgres_dsn

        report = run_agent2(
            input_path=args.input,
            output_dir=args.output_dir,
            deviation_threshold=args.deviation_threshold,
            postgres_dsn=postgres_dsn,
            write_postgres=postgres_dsn is not None,
        )
        print("Agente 2 MVP ejecutado")
        print(f"- Contratos de entrada: {report['rows']}")
        print(f"- Contratos con alguna señal: {report['activated_contract_rows']}")
        print(f"- Señales activadas: {report['activated_flags']}")
        print(f"- PostgreSQL: {'si' if postgres_dsn else 'no'}")
        print(f"- Reporte: {report['report_path']}")
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
        )

        print(f"run-batch [{result['status']}]")
        print(f"batch_id: {result['batch_id']}")
        print(f"agent1_executed: {result['agent1_executed']}")
        print(f"changed_sources: {result['changed_sources']}")
        if result.get("agent1_run_report_path"):
            print(f"agent1_report: {result['agent1_run_report_path']}")
        return 0

    parser.print_help()
    return 0
