from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agent1 import run_agent1

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

    started_at = datetime.now(UTC)
    batch_id = f"{run_mode}_{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    requested_place_datasets = (
        sorted(place_datasets) if place_datasets else DEFAULT_PLACE_DOWNLOAD_DATASETS
    )
    place_download = bool(place_download if place_download is not None else run_mode == "monthly")

    warnings: list[str] = []
    health_checks: list[dict[str, Any]] = []
    core_snapshots: list[dict[str, Any]] = [
        _snapshot_file("boe_raw", boe_input),
        _snapshot_file("opentender_raw", open_tender_input),
    ]
    health_checks.extend(
        [
            _health_check_from_snapshot(
                core_snapshots[0],
                label="BOE raw",
                required=True,
                blocking=True,
            ),
            _health_check_from_snapshot(
                core_snapshots[1],
                label="OpenTender raw",
                required=True,
                blocking=True,
            ),
        ]
    )

    place_targets: list[Any] = []
    if not manifest_path.exists():
        warnings.append(f"No existe manifiesto PLACE: {manifest_path}")
        health_checks.append(
            {
                "source_id": "place_manifest",
                "label": "PLACE manifest",
                "path": str(manifest_path),
                "required": False,
                "blocking": False,
                "exists": False,
                "status": "warning",
                "message": "No se pueden evaluar targets PLACE sin manifiesto.",
            }
        )
    else:
        try:
            place_targets = place_module.build_targets(
                place_module.load_manifest(manifest_path),
                year=year,
                dataset_ids=set(requested_place_datasets),
                include_docs=False,
                include_data=True,
                raw_dir=raw_dir,
            )
            health_checks.append(
                {
                    "source_id": "place_manifest",
                    "label": "PLACE manifest",
                    "path": str(manifest_path),
                    "required": False,
                    "blocking": False,
                    "exists": True,
                    "status": "ok",
                    "message": "Manifiesto PLACE legible.",
                }
            )
        except (KeyError, json.JSONDecodeError, OSError, ValueError) as exc:
            warnings.append(f"No se pudo leer manifiesto PLACE {manifest_path}: {exc}")
            health_checks.append(
                {
                    "source_id": "place_manifest",
                    "label": "PLACE manifest",
                    "path": str(manifest_path),
                    "required": False,
                    "blocking": False,
                    "exists": False,
                    "status": "warning",
                    "message": str(exc),
                }
            )

    for target in place_targets:
        if target.kind != "dataset":
            continue
        snapshot = _snapshot_file(f"place::{target.id}", target.output_path)
        core_snapshots.append(snapshot)
        blocking = not place_download
        health_check = _health_check_from_snapshot(
            snapshot,
            label=f"PLACE dataset {target.id}",
            required=blocking,
            blocking=blocking,
        )
        if not snapshot["exists"] and place_download:
            health_check["status"] = "planned_download"
            health_check["message"] = (
                "No existe localmente; se permite descarga PLACE durante run_agent1."
            )
        elif not snapshot["exists"]:
            warnings.append(f"Falta PLACE local {target.id} y --place-download no esta activado.")
        health_checks.append(health_check)

    datos_gob_snapshots = _snapshot_directory(prefix="datos_gob", base_dir=datos_gob_dir)
    health_checks.append(
        {
            "source_id": "datos_gob",
            "label": "datos.gob.es opcional",
            "path": str(datos_gob_dir),
            "required": False,
            "blocking": False,
            "exists": datos_gob_dir.exists(),
            "status": "ok" if datos_gob_dir.exists() or not include_datos_gob else "warning",
            "message": (
                f"{len(datos_gob_snapshots)} archivos detectados."
                if datos_gob_dir.exists()
                else "Directorio opcional no disponible."
            ),
        }
    )
    missing_required_inputs = _deduplicate_missing_inputs(
        _missing_required_from_health_checks(health_checks)
    )

    previous_state = _load_batch_state(batch_state_path)
    previous_snapshots = {
        entry["source_id"]: entry
        for entry in (previous_state.get("source_snapshots") if previous_state else [])
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
    has_blocking_inputs = bool(missing_required_inputs)
    run_agent1_now = (
        not has_blocking_inputs
        and (force or run_mode == "monthly" or source_has_changes)
    )

    run_agent1_report: dict[str, Any] | None = None
    if run_agent1_now:
        place_inputs: list[Path] = []
        if not place_download:
            place_inputs = [
                target.output_path for target in place_targets if target.kind == "dataset"
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

    status = (
        "blocked_missing_inputs"
        if has_blocking_inputs
        else "executed"
        if run_agent1_now
        else "skipped"
    )
    batch_manifest_path = batch_manifest_dir / run_mode / batch_id / "manifest.json"
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
        "health_checks": health_checks,
        "missing_required_inputs": missing_required_inputs,
        "warnings": warnings,
        "changed_sources": sorted(set(changed_sources)),
        "source_has_changes": source_has_changes,
        "agent1_executed": run_agent1_now,
        "status": status,
        "agent1_report": run_agent1_report,
        "batch_state_path": str(batch_state_path),
        "batch_manifest_path": str(batch_manifest_path),
        "derived_rebuild_plan": _build_derived_rebuild_plan(
            run_mode=run_mode,
            processed_dir=processed_dir,
            agent1_executed=run_agent1_now,
            blocked=has_blocking_inputs,
        ),
    }
    if run_agent1_report is not None:
        batch_manifest["agent1_run_report_path"] = run_agent1_report.get("agent1_run_report_path")

    batch_manifest["completed_at_utc"] = datetime.now(UTC).isoformat()

    batch_state_path.parent.mkdir(parents=True, exist_ok=True)
    batch_state_path.write_text(
        json.dumps(batch_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    batch_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    batch_manifest_path.write_text(
        json.dumps(batch_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return batch_manifest


def _health_check_from_snapshot(
    snapshot: dict[str, Any],
    *,
    label: str,
    required: bool,
    blocking: bool,
) -> dict[str, Any]:
    exists = bool(snapshot["exists"])
    return {
        "source_id": snapshot["source_id"],
        "label": label,
        "path": snapshot["path"],
        "required": required,
        "blocking": blocking,
        "exists": exists,
        "status": "ok" if exists else "missing",
        "message": "Disponible." if exists else "No existe en ruta local.",
    }


def _missing_required_from_health_checks(
    health_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "source_id": str(check["source_id"]),
            "label": str(check["label"]),
            "path": str(check["path"]),
            "message": str(check["message"]),
        }
        for check in health_checks
        if check.get("required") and check.get("blocking") and not check.get("exists")
    ]


def _deduplicate_missing_inputs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated: dict[str, dict[str, Any]] = {}
    for item in items:
        deduplicated[item["source_id"]] = item
    return list(deduplicated.values())


def _build_derived_rebuild_plan(
    *,
    run_mode: str,
    processed_dir: Path,
    agent1_executed: bool,
    blocked: bool,
) -> dict[str, Any]:
    canonical_path = processed_dir / "agent2_contracts_canonical.parquet"
    if blocked:
        downstream_status = "blocked_by_missing_inputs"
    elif run_mode == "monthly":
        downstream_status = "planned_if_canonical_exists"
    else:
        downstream_status = "not_planned_for_weekly_batch"
    return {
        "agent1": "executed" if agent1_executed else "blocked" if blocked else "skipped",
        "agent2_mvp": downstream_status,
        "agent3": downstream_status,
        "agent4": "manual_or_demo_only",
        "canonical_path": str(canonical_path),
        "canonical_exists": canonical_path.exists(),
    }


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

    parser = argparse.ArgumentParser(
        description="Orquesta lote semanal/mensual de fuentes de datos."
    )
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
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_PLACE_MANIFEST)
    parser.add_argument("--batch-state-path", type=Path, default=DEFAULT_BATCH_STATE_PATH)
    parser.add_argument("--batch-manifest-dir", type=Path, default=DEFAULT_BATCH_MANIFEST_DIR)
    parser.add_argument("--datos-gob-dir", type=Path, default=DEFAULT_DATOS_GOB_DIR)
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
        processed_dir=args.processed_dir,
        manifest_path=args.manifest_path,
        batch_state_path=args.batch_state_path,
        batch_manifest_dir=args.batch_manifest_dir,
        datos_gob_dir=args.datos_gob_dir,
        raw_dir=args.raw_dir,
        cleanup_downloads=args.cleanup_downloads,
    )

    status = result["status"]
    print(f"run-batch [{status}]")
    print(f"batch_id: {result['batch_id']}")
    print(f"run_mode: {result['run_mode']}")
    print(f"agent1_executed: {result['agent1_executed']}")
    print(f"changed_sources: {result['changed_sources']}")
    print(f"missing_required_inputs: {result['missing_required_inputs']}")
    print(f"manifest: {result['batch_manifest_path']}")
    if result.get("agent1_run_report_path"):
        print(f"agent1_report: {result['agent1_run_report_path']}")
    return 0 if status in {"executed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
