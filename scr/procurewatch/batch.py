from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from .agent1 import run_agent1
from .agent2 import run_agent2

DEFAULT_BOE_INPUT = Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv")
DEFAULT_OPEN_TENDER_INPUT = Path("data/raw/opentender/data-es-ocds-json.zip")
DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_PLACE_MANIFEST = Path("config/place_sources.json")
DEFAULT_BATCH_STATE_PATH = Path("data/processed/run_batch_state.json")
DEFAULT_BATCH_MANIFEST_DIR = Path("data/manifest/batches")
DEFAULT_DATOS_GOB_DIR = Path("data/raw/datos_gob")
DEFAULT_PLACE_DOWNLOAD_DATASETS = ["place_profiles", "place_aggregation"]


def run_batch(
    *,
    run_mode: str = "weekly",
    year: int = 2024,
    cpv_prefix: str = "71",
    force: bool = False,
    place_download: bool | None = None,
    place_datasets: list[str] | None = None,
    include_datos_gob: bool = True,
    boe_input: Path = DEFAULT_BOE_INPUT,
    open_tender_input: Path = DEFAULT_OPEN_TENDER_INPUT,
    open_tender_download_url: str | None = None,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    manifest_path: Path = DEFAULT_PLACE_MANIFEST,
    batch_state_path: Path = DEFAULT_BATCH_STATE_PATH,
    batch_manifest_dir: Path = DEFAULT_BATCH_MANIFEST_DIR,
    datos_gob_dir: Path = DEFAULT_DATOS_GOB_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    cleanup_downloads: bool = False,
) -> dict[str, Any]:
    from .data_sources import place as place_module
    if run_mode not in {"weekly", "monthly"}:
        raise ValueError(f"run_mode invalido: {run_mode}")
    if not boe_input.exists():
        raise FileNotFoundError(f"No existe BOE raw: {boe_input}")
    if not open_tender_input.exists():
        raise FileNotFoundError(f"No existe OpenTender raw: {open_tender_input}")

    started_at = datetime.now(UTC)
    batch_id = f"{run_mode}_{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    requested_place_datasets = sorted(place_datasets) if place_datasets else DEFAULT_PLACE_DOWNLOAD_DATASETS
    place_download = bool(place_download if place_download is not None else run_mode == "monthly")

    # Snapshots de entradas principales
    core_snapshots: list[dict[str, Any]] = [
        _snapshot_file("boe_raw", boe_input),
        _snapshot_file("opentender_raw", open_tender_input),
    ]

    # Snapshots de PLACE desde el manifiesto de fuentes.
    place_targets = place_module.build_targets(
        place_module.load_manifest(manifest_path),
        year=year,
        dataset_ids=set(requested_place_datasets),
        include_docs=False,
        include_data=True,
        raw_dir=raw_dir,
    )
    for target in place_targets:
        if target.kind == "dataset":
            core_snapshots.append(_snapshot_file(f"place::{target.id}", target.output_path))

    # Snapshots de apoyo con datos.gob.es para corroboración/fuente complementaria.
    datos_gob_snapshots = _snapshot_directory(
        prefix="datos_gob",
        base_dir=datos_gob_dir,
    )

    previous_state = _load_batch_state(batch_state_path)
    previous_output_snapshot_entries = (
        previous_state.get("output_snapshots") if previous_state else []
    )
    previous_snapshots = {
        entry["source_id"]: entry
        for entry in (previous_state.get("source_snapshots") if previous_state else [])
        if isinstance(entry, dict) and "source_id" in entry
    }
    previous_output_snapshots = {
        entry["source_id"]: entry
        for entry in (previous_output_snapshot_entries or [])
        if isinstance(entry, dict) and "source_id" in entry
    }

    changed_sources: list[str] = []
    for snapshot in core_snapshots:
        old = previous_snapshots.get(snapshot["source_id"])
        if not _same_snapshot(snapshot, old):
            changed_sources.append(snapshot["source_id"])

    if include_datos_gob:
        for snapshot in datos_gob_snapshots:
            old = previous_snapshots.get(snapshot["source_id"])
            if not _same_snapshot(snapshot, old):
                changed_sources.append(snapshot["source_id"])

    source_has_changes = bool(changed_sources)

    # Cobertura semanal: evita re-ejecuciones completas si todo igual.
    run_agent1_now = force or run_mode == "monthly" or source_has_changes

    run_agent1_report: dict[str, Any] | None = None
    agent1_output_snapshots: list[dict[str, Any]] = []
    if run_agent1_now:
        place_inputs: list[Path] = []
        if not place_download:
            place_inputs = [
                target.output_path
                for target in place_targets
                if target.kind == "dataset"
            ]
        run_agent1_report = run_agent1(
            boe_input=boe_input,
            open_tender_input=open_tender_input,
            open_tender_download_url=open_tender_download_url,
            place_inputs=place_inputs,
            raw_dir=raw_dir,
            cleanup_downloads=cleanup_downloads,
            output_dir=processed_dir,
            cpv_prefix=cpv_prefix,
            year=year,
            place_download=place_download,
            place_datasets=requested_place_datasets,
        )
        agent1_output_snapshots = _agent1_output_snapshots(run_agent1_report)
    else:
        run_agent1_report = None

    canonical_snapshot = next(
        (snapshot for snapshot in agent1_output_snapshots if snapshot["source_id"] == "agent1::canonical_agent2"),
        None,
    )
    canonical_has_changes = bool(
        canonical_snapshot
        and not _same_snapshot(canonical_snapshot, previous_output_snapshots.get("agent1::canonical_agent2"))
    )

    run_agent2_now = force or run_mode == "monthly" or canonical_has_changes

    run_agent2_report: dict[str, Any] | None = None
    agent2_output_snapshots: list[dict[str, Any]] = []
    if run_agent2_now and canonical_snapshot is not None:
        canonical_path = Path(canonical_snapshot["path"])
        run_agent2_report = run_agent2(
            input_path=canonical_path,
            output_dir=processed_dir,
        )
        agent2_output_snapshots = _agent2_output_snapshots(run_agent2_report)

    output_snapshots = agent1_output_snapshots + agent2_output_snapshots
    freeze_manifest: dict[str, Any] | None = None
    freeze_manifest_path: Path | None = None
    if run_mode == "monthly" or force:
        freeze_manifest = {
            "freeze_id": batch_id,
            "freeze_mode": "final" if run_mode == "monthly" else "forced",
            "batch_id": batch_id,
            "run_mode": run_mode,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "year": year,
            "cpv_prefix": cpv_prefix,
            "source_snapshots": core_snapshots + (datos_gob_snapshots if include_datos_gob else []),
            "output_snapshots": output_snapshots,
            "agent1_run_report_path": run_agent1_report.get("agent1_run_report_path")
            if run_agent1_report
            else None,
            "agent2_run_report_path": run_agent2_report.get("report_path") if run_agent2_report else None,
        }
        freeze_manifest_path = batch_manifest_dir / run_mode / batch_id / "freeze_manifest.json"
        freeze_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        freeze_manifest_path.write_text(
            json.dumps(freeze_manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    batch_manifest = {
        "batch_id": batch_id,
        "run_mode": run_mode,
        "executed_at_utc": started_at.isoformat(),
        "year": year,
        "cpv_prefix": cpv_prefix,
        "core_inputs": {
            "boe_input": str(boe_input),
            "open_tender_input": str(open_tender_input),
            "place_datasets": requested_place_datasets,
            "place_download": place_download,
            "raw_dir": str(raw_dir),
            "include_datos_gob": include_datos_gob,
        },
        "source_snapshots": core_snapshots + (datos_gob_snapshots if include_datos_gob else []),
        "changed_sources": sorted(set(changed_sources)),
        "source_has_changes": source_has_changes,
        "agent1_executed": run_agent1_now,
        "agent2_executed": run_agent2_now,
        "status": "executed" if (run_agent1_now or run_agent2_now) else "skipped",
        "agent1_report": run_agent1_report,
        "agent2_report": run_agent2_report,
        "output_snapshots": output_snapshots,
        "freeze_status": "frozen" if freeze_manifest is not None else "not_frozen",
        "freeze_manifest": freeze_manifest,
    }
    if run_agent1_report is not None:
        batch_manifest["agent1_run_report_path"] = run_agent1_report.get("agent1_run_report_path")
    if run_agent2_report is not None:
        batch_manifest["agent2_run_report_path"] = run_agent2_report.get("report_path")
    if freeze_manifest_path is not None:
        batch_manifest["freeze_manifest_path"] = str(freeze_manifest_path)

    completed_at = datetime.now(UTC)
    batch_manifest["completed_at_utc"] = completed_at.isoformat()

    previous_state_path = batch_state_path
    previous_state_path.parent.mkdir(parents=True, exist_ok=True)
    previous_state_path.write_text(
        json.dumps(batch_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    batch_manifest_path = batch_manifest_dir / run_mode / batch_id / "manifest.json"
    batch_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    batch_manifest_path.write_text(
        json.dumps(batch_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return batch_manifest


def _agent1_output_snapshots(report: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    canonical = report.get("canonical_agent2")
    if isinstance(canonical, dict) and canonical.get("path"):
        snapshots.append(_snapshot_file("agent1::canonical_agent2", Path(canonical["path"])))
    report_path = report.get("agent1_run_report_path")
    if report_path:
        snapshots.append(_snapshot_file("agent1::run_report", Path(report_path)))
    return snapshots


def _agent2_output_snapshots(report: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    outputs = report.get("outputs")
    if isinstance(outputs, dict):
        for output_name, output_path in outputs.items():
            if output_path:
                snapshots.append(_snapshot_file(f"agent2::{output_name}", Path(output_path)))
    report_path = report.get("report_path")
    if report_path:
        snapshots.append(_snapshot_file("agent2::run_report", Path(report_path)))
    return snapshots


def _snapshot_file(
    source_id: str,
    path: Path,
) -> dict[str, Any]:
    if not path.exists():
        return {
            "source_id": source_id,
            "path": str(path),
            "exists": False,
            "size_bytes": None,
            "sha256": None,
            "modified_utc": None,
        }

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return {
        "source_id": source_id,
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
        "modified_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
    }


def _snapshot_directory(
    *,
    prefix: str,
    base_dir: Path,
) -> list[dict[str, Any]]:
    if not base_dir.exists():
        return []

    snapshots: list[dict[str, Any]] = []
    for path in sorted(base_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base_dir).as_posix().replace("/", "::")
        snapshots.append(
            {
                **_snapshot_file(f"{prefix}::{rel}", path),
            }
        )
    return snapshots


def _same_snapshot(candidate: dict[str, Any], previous: dict[str, Any] | None) -> bool:
    if previous is None:
        return False
    if candidate["exists"] != previous.get("exists"):
        return False
    if candidate["size_bytes"] != previous.get("size_bytes"):
        return False
    if candidate["sha256"] != previous.get("sha256"):
        return False
    return True


def _load_batch_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        return {}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Orquesta lote semanal/mensual de fuentes de datos.")
    parser.add_argument("--run-mode", default="weekly", choices=["weekly", "monthly"])
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--cpv-prefix", default="71")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--place-download", action="store_true")
    parser.add_argument("--place-datasets", nargs="*", default=None)
    parser.add_argument("--no-datos-gob", action="store_true")
    parser.add_argument("--boe-input", type=Path, default=DEFAULT_BOE_INPUT)
    parser.add_argument("--opentender-input", type=Path, default=DEFAULT_OPEN_TENDER_INPUT)
    parser.add_argument("--opentender-download-url", type=str, default=None)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--cleanup-downloads", action="store_true")
    args = parser.parse_args(argv)

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
        open_tender_download_url=args.opentender_download_url,
        raw_dir=args.raw_dir,
        cleanup_downloads=args.cleanup_downloads,
    )

    status = result["status"]
    print(f"run-batch [{status}]")
    print(f"batch_id: {result['batch_id']}")
    print(f"run_mode: {result['run_mode']}")
    print(f"agent1_executed: {result['agent1_executed']}")
    print(f"changed_sources: {result['changed_sources']}")
    if result.get("agent1_run_report_path"):
        print(f"agent1_report: {result['agent1_run_report_path']}")
    return 0 if status in {"executed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
