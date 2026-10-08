from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

DEFAULT_BOE_INPUT = Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv")
DEFAULT_OPENTENDER_INPUT = Path("data/raw/opentender/data-es-ocds-json.zip")
DEFAULT_PLACE_INPUTS = [
    Path("data/raw/place/profiles/licitacionesPerfilesContratanteCompleto3_2024.zip"),
    Path("data/raw/place/aggregation/PlataformasAgregadasSinMenores_2024.zip"),
]
DEFAULT_SAMPLE_DIR = Path("data/synthetic/agent1_sample")


def make_agent1_sample(
    *,
    output_dir: Path = DEFAULT_SAMPLE_DIR,
    rows: int = 1000,
    year: int = 2024,
    cpv_prefix: str = "71",
    boe_input: Path = DEFAULT_BOE_INPUT,
    opentender_input: Path = DEFAULT_OPENTENDER_INPUT,
    place_inputs: list[Path] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    if rows <= 0:
        raise ValueError("rows debe ser mayor que 0")

    output_dir.mkdir(parents=True, exist_ok=True)
    place_inputs = place_inputs or DEFAULT_PLACE_INPUTS

    boe_output = output_dir / "boe_sample.csv"
    opentender_output = output_dir / "opentender_2024_sample.zip"
    place_outputs = [output_dir / f"{path.stem}_sample.zip" for path in place_inputs]

    report = {
        "output_dir": str(output_dir),
        "rows_requested_per_source": rows,
        "year": year,
        "cpv_prefix": cpv_prefix,
        "boe": _make_boe_sample(boe_input, boe_output, rows, cpv_prefix, overwrite=overwrite),
        "opentender": _make_opentender_sample(
            opentender_input,
            opentender_output,
            rows,
            year,
            cpv_prefix,
            overwrite=overwrite,
        ),
        "place": [
            _make_place_sample(input_path, output_path, rows, cpv_prefix, overwrite=overwrite)
            for input_path, output_path in zip(place_inputs, place_outputs, strict=True)
        ],
    }

    report["agent1_command"] = (
        f"procurewatch run-agent1 --boe-input {boe_output} "
        f"--opentender-input {opentender_output} "
        f"--place-inputs {' '.join(str(path) for path in place_outputs)} "
        f"--output-dir data/processed_sample --year {year} --cpv-prefix {cpv_prefix}"
    )
    (output_dir / "sample_manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def _make_boe_sample(
    input_path: Path,
    output_path: Path,
    rows: int,
    cpv_prefix: str,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    if output_path.exists() and not overwrite:
        return _existing_output_report(input_path, output_path)
    if not input_path.exists():
        raise FileNotFoundError(f"No existe BOE input: {input_path}")

    cpv_re = _cpv_regex(cpv_prefix)
    selected = 0
    scanned = 0
    with (
        input_path.open("r", encoding="utf-8", errors="replace", newline="") as source,
        output_path.open("w", encoding="utf-8", newline="") as target,
    ):
        header = source.readline()
        target.write(header)
        for line in source:
            scanned += 1
            if cpv_re is not None and not cpv_re.search(line):
                continue
            target.write(line)
            selected += 1
            if selected >= rows:
                break

    return _created_output_report(input_path, output_path, scanned, selected)


def _make_opentender_sample(
    input_path: Path,
    output_path: Path,
    rows: int,
    year: int,
    cpv_prefix: str,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    if output_path.exists() and not overwrite:
        return _existing_output_report(input_path, output_path)
    if not input_path.exists():
        raise FileNotFoundError(f"No existe OpenTender input: {input_path}")

    entry_name = f"data-es-ocds-{year}.json"
    cpv_re = _opentender_cpv_regex(cpv_prefix)
    selected = 0
    scanned = 0
    with zipfile.ZipFile(input_path, "r") as source_zip:
        if entry_name not in source_zip.namelist():
            raise FileNotFoundError(f"No existe {entry_name} dentro de {input_path}")
        with (
            source_zip.open(entry_name, "r") as raw,
            zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as target_zip,
        ):
            buffer = io.StringIO()
            for raw_line in io.TextIOWrapper(raw, encoding="utf-8"):
                scanned += 1
                if cpv_re is not None and not cpv_re.search(raw_line):
                    continue
                buffer.write(raw_line)
                selected += 1
                if selected >= rows:
                    break
            target_zip.writestr(entry_name, buffer.getvalue())

    return _created_output_report(input_path, output_path, scanned, selected)


def _make_place_sample(
    input_path: Path,
    output_path: Path,
    rows: int,
    cpv_prefix: str,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    if output_path.exists() and not overwrite:
        return _existing_output_report(input_path, output_path)
    if not input_path.exists():
        raise FileNotFoundError(f"No existe PLACE input: {input_path}")

    from .data_sources.place_normalize import _entry_may_contain_cpv_prefix, _iter_atom_entry_chunks

    selected = 0
    scanned = 0
    chunks: list[bytes] = []
    with zipfile.ZipFile(input_path, "r") as source_zip:
        atom_files = sorted(
            name for name in source_zip.namelist() if name.lower().endswith(".atom")
        )
        for atom_name in atom_files:
            raw_bytes = source_zip.read(atom_name)
            for entry_bytes in _iter_atom_entry_chunks(raw_bytes):
                scanned += 1
                if cpv_prefix != "all" and not _entry_may_contain_cpv_prefix(
                    entry_bytes, cpv_prefix
                ):
                    continue
                chunks.append(entry_bytes)
                selected += 1
                if selected >= rows:
                    break
            if selected >= rows:
                break

    sample_feed = b"\n".join(chunks)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
        target_zip.writestr("sample.atom", sample_feed)

    return _created_output_report(input_path, output_path, scanned, selected)


def _cpv_regex(cpv_prefix: str) -> re.Pattern[str] | None:
    if cpv_prefix == "all":
        return None
    return re.compile(rf"\b{re.escape(cpv_prefix)}\d{{6}}\b")


def _opentender_cpv_regex(cpv_prefix: str) -> re.Pattern[str] | None:
    if cpv_prefix == "all":
        return None
    return re.compile(rf'"id"\s*:\s*"{re.escape(cpv_prefix)}\d+')


def _created_output_report(
    input_path: Path,
    output_path: Path,
    scanned: int,
    selected: int,
) -> dict[str, Any]:
    return {
        "input": str(input_path),
        "output": str(output_path),
        "scanned_rows_or_entries": scanned,
        "selected_rows_or_entries": selected,
        "size_bytes": output_path.stat().st_size,
        "created": True,
    }


def _existing_output_report(input_path: Path, output_path: Path) -> dict[str, Any]:
    return {
        "input": str(input_path),
        "output": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "created": False,
        "reason": "exists",
    }
