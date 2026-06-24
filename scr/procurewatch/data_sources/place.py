from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import requests

PARSER_VERSION = "1.0.0"
DEFAULT_MANIFEST = Path("config/place_sources.json")
DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_TIMEOUT_SECONDS = 60
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class DownloadTarget:
    id: str
    name: str
    url: str
    output_path: Path
    kind: str
    priority: str | None = None
    role: str | None = None


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def build_targets(
    manifest: dict[str, Any],
    *,
    year: int,
    dataset_ids: set[str] | None = None,
    include_docs: bool = True,
    include_data: bool = True,
    raw_dir: Path = DEFAULT_RAW_DIR,
) -> list[DownloadTarget]:
    targets: list[DownloadTarget] = []

    if include_data:
        for dataset in manifest["datasets"]:
            dataset_id = dataset["id"]
            if dataset_ids and dataset_id not in dataset_ids:
                continue

            if "file_url" in dataset:
                url = dataset["file_url"]
                suffix = Path(url).suffix or ".bin"
                filename = f"{dataset_id}{suffix}"
            else:
                if year < int(dataset["first_year"]):
                    continue
                url = dataset["annual_url_pattern"].format(year=year)
                filename = Path(url).name

            targets.append(
                DownloadTarget(
                    id=dataset_id,
                    name=dataset["name"],
                    url=url,
                    output_path=raw_dir / dataset["raw_subdir"] / filename,
                    kind="dataset",
                    priority=dataset.get("priority"),
                    role=dataset.get("role"),
                )
            )

    if include_docs:
        for document in manifest["reference_documents"]:
            url = document["url"]
            targets.append(
                DownloadTarget(
                    id=document["id"],
                    name=document["name"],
                    url=url,
                    output_path=raw_dir / document["raw_subdir"] / Path(url).name,
                    kind="reference_document",
                )
            )

    return targets


def inspect_targets(targets: list[DownloadTarget]) -> list[dict[str, Any]]:
    return [inspect_target(target) for target in targets]


def inspect_target(target: DownloadTarget) -> dict[str, Any]:
    info: dict[str, Any] = target_to_dict(target)
    try:
        response = requests.head(
            target.url,
            allow_redirects=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={"User-Agent": "ProcureWatchAnalytics/0.1"},
        )
        if response.status_code in {403, 405}:
            response = requests.get(
                target.url,
                stream=True,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                headers={"User-Agent": "ProcureWatchAnalytics/0.1"},
            )
            response.close()

        info.update(
            {
                "status_code": response.status_code,
                "content_length": parse_content_length(response.headers.get("content-length")),
                "content_type": response.headers.get("content-type"),
                "final_url": response.url,
                "available": response.ok,
            }
        )
    except requests.RequestException as exc:
        info.update({"available": False, "error": str(exc)})

    return info


def download_targets(
    targets: list[DownloadTarget],
    *,
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    results = []
    for target in targets:
        results.append(download_target(target, overwrite=overwrite))
    return results


def download_target(target: DownloadTarget, *, overwrite: bool = False) -> dict[str, Any]:
    target.output_path.parent.mkdir(parents=True, exist_ok=True)
    if target.output_path.exists() and not overwrite:
        return {
            **target_to_dict(target),
            "downloaded": False,
            "skipped": True,
            "reason": "exists",
            "size_bytes": target.output_path.stat().st_size,
            "sha256": sha256_file(target.output_path),
        }

    last_error: str | None = None
    temp_path: Path | None = None
    for attempt in range(1, 4):
        try:
            response = requests.get(
                target.url,
                stream=True,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                headers={"User-Agent": "ProcureWatchAnalytics/0.1"},
            )
            response.raise_for_status()

            digest = hashlib.sha256()
            size = 0
            temp_path = target.output_path.with_suffix(
                f"{target.output_path.suffix}.tmp" if target.output_path.suffix else ".tmp"
            )
            with temp_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    file.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)

            temp_path.replace(target.output_path)
            return {
                **target_to_dict(target),
                "downloaded": True,
                "skipped": False,
                "attempts": attempt,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "size_bytes": size,
                "sha256": digest.hexdigest(),
            }
        except requests.RequestException as exc:
            last_error = str(exc)
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
            if attempt < 3:
                time.sleep(1.5)
                continue
            break

    return {
        **target_to_dict(target),
        "downloaded": False,
        "attempts": 3,
        "skipped": False,
        "status_code": None,
        "content_type": None,
        "size_bytes": 0,
        "sha256": None,
        "error": last_error,
    }


def write_report(report: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def target_to_dict(target: DownloadTarget) -> dict[str, Any]:
    return {
        "id": target.id,
        "name": target.name,
        "kind": target.kind,
        "priority": target.priority,
        "role": target.role,
        "url": target.url,
        "output_path": str(target.output_path),
    }


def parse_content_length(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gestiona descargas oficiales de PLACE.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=None,
        help="IDs concretos del manifiesto. Si se omite, usa todos los datasets compatibles.",
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--no-docs", action="store_true")
    parser.add_argument("--no-data", action="store_true")
    parser.add_argument("--inspect", action="store_true", help="Solo comprueba disponibilidad.")
    parser.add_argument("--download", action="store_true", help="Descarga los objetivos.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/raw/place_download_report.json"),
    )
    args = parser.parse_args(argv)

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

    report = (
        inspect_targets(targets)
        if args.inspect
        else download_targets(
            targets,
            overwrite=args.overwrite,
        )
    )
    write_report(report, args.report)

    for item in report:
        status = item.get("status_code", "n/a")
        size = item.get("content_length") or item.get("size_bytes") or "unknown"
        marker = "OK" if item.get("available", item.get("downloaded", False)) else "WARN"
        print(f"[{marker}] {item['id']} status={status} size={size} -> {item['output_path']}")

    print(f"Reporte: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
