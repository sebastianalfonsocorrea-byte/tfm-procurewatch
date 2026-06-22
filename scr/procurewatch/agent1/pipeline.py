from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

DEFAULT_MANIFEST = Path("config/place_sources.json")


def run_agent1(
    *,
    boe_input: Path,
    open_tender_input: Path,
    open_tender_download_url: str | None = None,
    place_inputs: list[Path],
    buyer_catalog_path: Path | None = None,
    raw_dir: Path = Path("data/raw"),
    cleanup_downloads: bool = False,
    output_dir: Path = Path("data/processed"),
    cpv_prefix: str = "71",
    year: int = 2024,
    place_download: bool = False,
    place_datasets: list[str] | None = None,
    limit_boe: int | None = None,
    limit_place: int | None = None,
    limit_ot: int | None = None,
    force_rebuild: bool = False,
    postgres_dsn: str | None = None,
    write_postgres: bool = False,
) -> dict[str, Any]:
    if place_download:
        from ..data_sources.place import build_targets, download_targets, load_manifest
    from ..data_sources import boe as boe_source
    from ..data_sources import opentender as opentender_source
    from ..data_sources import place_normalize as place_source

    if not boe_input.exists():
        raise FileNotFoundError(f"No existe BOE input: {boe_input}")
    if buyer_catalog_path is not None and not buyer_catalog_path.exists():
        raise FileNotFoundError(f"No existe buyer catalog input: {buyer_catalog_path}")
    if not place_inputs and not place_download:
        raise ValueError(
            "Debes indicar al menos un fichero PLACE de entrada o usar --place-download."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    reports: dict[str, Any] = {}
    selected_place_inputs = list(place_inputs)
    downloaded_targets: list[Path] = []
    downloaded_opentender_inputs: list[Path] = []
    effective_open_tender_input = open_tender_input

    if open_tender_download_url:
        from ..data_sources.opentender import download_opentender_zip

        effective_open_tender_input = raw_dir / "opentender" / "data-es-ocds-json.zip"
        opentender_download_report = download_opentender_zip(
            url=open_tender_download_url,
            output_path=effective_open_tender_input,
            overwrite=True,
        )
        reports["opentender_download"] = opentender_download_report
        effective_open_tender_input = Path(opentender_download_report["output_path"])
        if opentender_download_report.get("downloaded"):
            downloaded_opentender_inputs = [effective_open_tender_input]
    if not effective_open_tender_input.exists():
        raise FileNotFoundError(f"No existe OpenTender input: {effective_open_tender_input}")

    if place_download:
        manifest = load_manifest(DEFAULT_MANIFEST)
        targets = build_targets(
            manifest,
            year=year,
            dataset_ids=set(place_datasets) if place_datasets else None,
            include_docs=False,
            include_data=True,
            raw_dir=raw_dir,
        )
        download_report = download_targets(targets, overwrite=True)
        downloaded_targets = [target.output_path for target in targets if target.kind == "dataset"]
        if not place_inputs:
            selected_place_inputs = downloaded_targets
        reports["place_download"] = download_report

    for path in selected_place_inputs:
        if not path.exists():
            raise FileNotFoundError(f"No existe PLACE input: {path}")

    input_artifacts = {
        "boe": _input_artifact_metadata(
            boe_input, compute_sha=force_rebuild or limit_boe is not None
        ),
        "opentender": _input_artifact_metadata(
            effective_open_tender_input,
            compute_sha=force_rebuild or limit_ot is not None,
        ),
        "place_files": [
            _input_artifact_metadata(path, compute_sha=force_rebuild or limit_place is not None)
            for path in selected_place_inputs
        ],
        "buyer_catalog": _input_artifact_metadata(buyer_catalog_path, compute_sha=force_rebuild)
        if buyer_catalog_path is not None
        else None,
    }
    reports["inputs"] = {
        "boe_input": str(boe_input),
        "open_tender_input": str(effective_open_tender_input),
        "open_tender_download_url": open_tender_download_url,
        "place_inputs": [str(path) for path in selected_place_inputs],
        "downloaded_targets": [str(path) for path in downloaded_targets],
        "downloaded_opentender_inputs": [str(path) for path in downloaded_opentender_inputs],
        "year": year,
        "cpv_prefix": cpv_prefix,
        "limits": {"boe": limit_boe, "place": limit_place, "opentender": limit_ot},
        "force_rebuild": force_rebuild,
        "run_at_utc": datetime.now(UTC).isoformat(),
        "input_artifacts": input_artifacts,
        "parser_versions": {
            "agent1": "1.0.0",
            "boe": getattr(boe_source, "PARSER_VERSION", "unknown"),
            "place": getattr(place_source, "PARSER_VERSION", "unknown"),
            "opentender": getattr(opentender_source, "PARSER_VERSION", "unknown"),
        },
    }

    from ..data_sources.boe import normalize_boe_file
    from ..data_sources.opentender import normalize_opentender_file
    from ..data_sources.place_normalize import normalize_place_archives

    boe_report_path = output_dir / "data_quality_report.json"
    boe_cached = _can_reuse_boe(
        output_dir, input_artifacts["boe"], boe_report_path, limit_boe, force_rebuild
    )
    if boe_cached:
        reports["boe"] = _cached_report(boe_report_path, source="boe")
        _hydrate_artifact_from_report(input_artifacts["boe"], reports["boe"])
    else:
        input_artifacts["boe"] = _input_artifact_metadata(boe_input, compute_sha=True)
        reports["boe"] = normalize_boe_file(boe_input, output_dir=output_dir, limit=limit_boe)

    place_report_path = output_dir / "contracts_place_quality.json"
    place_cached = _can_reuse_place(
        output_dir,
        input_artifacts["place_files"],
        place_report_path,
        limit_place,
        force_rebuild,
        place_download,
    )
    if place_cached:
        reports["place"] = _cached_report(place_report_path, source="place")
    else:
        input_artifacts["place_files"] = [
            _input_artifact_metadata(path, compute_sha=True) for path in selected_place_inputs
        ]
        reports["place"] = normalize_place_archives(
            selected_place_inputs,
            output_dir=output_dir,
            cpv_prefix=cpv_prefix,
            limit=limit_place,
            progress_every=0,
        )

    opentender_report_path = output_dir / f"contracts_opentender_{year}_quality.json"
    opentender_cached = _can_reuse_opentender(
        output_dir,
        input_artifacts["opentender"],
        opentender_report_path,
        year,
        cpv_prefix,
        limit_ot,
        force_rebuild,
    )
    if opentender_cached:
        reports["opentender"] = _cached_report(opentender_report_path, source="opentender")
        _hydrate_artifact_from_report(input_artifacts["opentender"], reports["opentender"])
    else:
        input_artifacts["opentender"] = _input_artifact_metadata(
            effective_open_tender_input, compute_sha=True
        )
        reports["opentender"] = normalize_opentender_file(
            input_path=effective_open_tender_input,
            output_dir=output_dir,
            year=year,
            cpv_prefix=cpv_prefix,
            limit=limit_ot,
        )

    coverage = build_source_coverage(
        output_dir=output_dir,
        cpv_prefix=cpv_prefix,
        year=year,
    )
    canonical = build_agent2_canonical_dataset(
        output_dir=output_dir,
        cpv_prefix=cpv_prefix,
        year=year,
    )
    from .analytical_dataset import build_analytical_datasets

    analytical = build_analytical_datasets(
        canonical_path=Path(canonical["path"]),
        output_dir=output_dir,
        buyer_catalog_path=buyer_catalog_path,
        postgres_dsn=postgres_dsn,
        write_postgres=write_postgres,
    )
    quality_summary = build_agent1_quality_summary(
        output_dir=output_dir,
        coverage=coverage,
        canonical=canonical,
    )
    reports["pipeline"] = {
        "agent_dir": str(Path(__file__).resolve()),
        "output_dir": str(output_dir),
        "cpv_prefix": cpv_prefix,
        "year": year,
    }
    reports["agent1_run_report_path"] = str(output_dir / "agent1_run_report.json")
    reports["coverage"] = coverage
    reports["canonical_agent2"] = canonical
    reports["analytical_datasets"] = analytical
    reports["quality_summary"] = quality_summary
    if analytical.get("postgres_write") is not None:
        reports["postgres_write"] = analytical["postgres_write"]

    (output_dir / "agent1_run_report.json").write_text(
        json.dumps(reports, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if cleanup_downloads and (downloaded_targets or downloaded_opentender_inputs):
        for path in downloaded_targets:
            if path.exists():
                path.unlink()
        _cleanup_empty_parents(downloaded_targets, stop_dir=raw_dir)
        for path in downloaded_opentender_inputs:
            if path.exists():
                path.unlink()
        _cleanup_empty_parents(downloaded_opentender_inputs, stop_dir=raw_dir)
    return reports


def build_source_coverage(
    *,
    output_dir: Path,
    cpv_prefix: str,
    year: int | None = None,
) -> dict[str, Any]:
    import pandas as pd

    boe_award_lines_path = output_dir / "contracts_boe_award_lines_cpv71.parquet"
    boe_path = (
        boe_award_lines_path
        if boe_award_lines_path.exists()
        else output_dir / "contracts_boe_cpv71.parquet"
    )
    place_path = output_dir / "contracts_place_cpv71.parquet"
    op_path = output_dir / f"contracts_opentender_{year or 'all'}_cpv{cpv_prefix}.parquet"

    boe_df = _read_parquet_columns(
        boe_path, ["file_number", "institution", "buyer_name", "publication_date", "contract_id"]
    )
    place_df = _read_parquet_columns(
        place_path,
        [
            "contract_folder_id",
            "source_dataset",
            "buyer_name",
            "buyer_dir3",
            "published_date",
            "source_entry_id",
        ],
    )
    op_df = _read_parquet_columns(
        op_path,
        ["source_record_id", "source_file", "buyer_name", "publication_date", "source_entry_id"],
    )

    boe_key_series = _build_contract_keys(
        boe_df,
        source="boe",
        id_columns=("file_number", "institution", "buyer_name", "publication_date"),
    )
    place_key_series = _build_contract_keys(
        place_df,
        source="place",
        id_columns=(
            "contract_folder_id",
            "source_dataset",
            "buyer_name",
            "buyer_dir3",
            "published_date",
        ),
    )
    op_key_series = _build_contract_keys(
        op_df,
        source="opentender",
        id_columns=("source_record_id", "source_file", "buyer_name", "publication_date"),
    )

    boe_keys = set(boe_key_series.dropna().tolist())
    place_keys = set(place_key_series.dropna().tolist())
    op_keys = set(op_key_series.dropna().tolist())

    key_rows = _build_universe_rows_from_sets(boe_keys, place_keys, op_keys)
    key_path = output_dir / "agent1_contract_key_coverage.parquet"
    key_df = pd.DataFrame(key_rows)
    key_df.to_parquet(key_path, index=False)
    key_df.head(500).to_csv(output_dir / "agent1_contract_key_coverage_preview.csv", index=False)

    return {
        "contract_key_coverage_path": str(key_path),
        "boe_contract_keys": len(boe_keys),
        "place_contract_keys": len(place_keys),
        "op_contract_keys": len(op_keys),
        "intersection_boe_place": len(boe_keys & place_keys),
        "intersection_boe_opentender": len(boe_keys & op_keys),
        "intersection_place_opentender": len(place_keys & op_keys),
        "universe_contract_keys": len(set(key_df["contract_key_canon"].tolist())),
        "only_in_boe": int(
            (
                key_df["present_in_boe"]
                & ~key_df["present_in_place"]
                & ~key_df["present_in_opentender"]
            ).sum()
        ),
        "only_in_place": int(
            (
                ~key_df["present_in_boe"]
                & key_df["present_in_place"]
                & ~key_df["present_in_opentender"]
            ).sum()
        ),
        "only_in_opentender": int(
            (
                ~key_df["present_in_boe"]
                & ~key_df["present_in_place"]
                & key_df["present_in_opentender"]
            ).sum()
        ),
        "present_in_all": int(
            (
                key_df["present_in_boe"]
                & key_df["present_in_place"]
                & key_df["present_in_opentender"]
            ).sum()
        ),
    }


def build_agent2_canonical_dataset(
    *,
    output_dir: Path,
    cpv_prefix: str,
    year: int | None = None,
) -> dict[str, Any]:
    import pandas as pd

    boe_award_lines_path = output_dir / "contracts_boe_award_lines_cpv71.parquet"
    boe_path = (
        boe_award_lines_path
        if boe_award_lines_path.exists()
        else output_dir / "contracts_boe_cpv71.parquet"
    )
    place_path = output_dir / "contracts_place_cpv71.parquet"
    op_path = output_dir / f"contracts_opentender_{year or 'all'}_cpv{cpv_prefix}.parquet"

    boe_columns = [
        "contract_id",
        "notice_id",
        "file_number",
        "institution",
        "buyer_name",
        "publication_date",
        "supplier_name",
        "object",
        "procedure",
        "estimated_value_eur",
        "awarded_value_eur",
        "cpv_codes_raw",
        "cpv_code_list",
        "source_file",
    ]
    place_columns = [
        "source_entry_id",
        "source_dataset",
        "contract_folder_id",
        "buyer_name",
        "buyer_dir3",
        "published_date",
        "winning_party_name",
        "winning_party_nif",
        "contract_title",
        "procedure_code",
        "award_date",
        "estimated_overall_amount",
        "total_amount",
        "cpv_codes_raw",
        "cpv_code_list",
        "source_file",
    ]
    opentender_columns = [
        "source_record_id",
        "source_entry_id",
        "source_file",
        "buyer_name",
        "buyer_id",
        "publication_date",
        "awarded_supplier_name",
        "awarded_supplier_nif",
        "contract_title",
        "procedure_code",
        "award_date",
        "estimated_amount_raw",
        "awarded_amount_raw",
        "cpv_codes_raw",
        "cpv_code_list",
    ]

    frames = [
        _canonical_from_boe(_read_parquet_columns(boe_path, boe_columns)),
        _canonical_from_place(_read_parquet_columns(place_path, place_columns)),
        _canonical_from_opentender(_read_parquet_columns(op_path, opentender_columns)),
    ]
    dataframe = (
        pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
        if any(not frame.empty for frame in frames)
        else pd.DataFrame(columns=CANONICAL_AGENT2_COLUMNS)
    )

    if not dataframe.empty:
        dataframe = dataframe[CANONICAL_AGENT2_COLUMNS].copy()
        dataframe["contract_key_canon"] = _norm_text(dataframe["contract_key_canon"])
        dataframe = dataframe[dataframe["contract_key_canon"].astype("string").str.strip() != ""]
        dataframe = dataframe.drop_duplicates(subset=["source", "contract_key_canon"])
        string_columns = [
            "contract_key_canon",
            "source",
            "source_record_id",
            "source_notice_id",
            "source_tender_id",
            "source_dataset",
            "buyer_name",
            "buyer_id",
            "supplier_name",
            "supplier_id",
            "contract_title",
            "procedure",
            "publication_date",
            "award_date",
            "cpv_codes_raw",
            "source_file",
        ]
        for column in string_columns:
            dataframe[column] = dataframe[column].astype("string").fillna("")
        dataframe["cpv_code_list"] = (
            dataframe["cpv_code_list"].map(_jsonish).astype("string").fillna("")
        )
        numeric_columns = ["estimated_value_eur", "awarded_value_eur"]
        for column in numeric_columns:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")

    parquet_path = output_dir / "agent2_contracts_canonical.parquet"
    preview_path = output_dir / "agent2_contracts_canonical_preview.csv"
    schema_path = output_dir / "agent2_contracts_canonical_schema.json"

    dataframe.to_parquet(parquet_path, index=False)
    dataframe.head(500).to_csv(preview_path, index=False, encoding="utf-8")
    schema = _agent2_schema()
    schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "path": str(parquet_path),
        "preview_path": str(preview_path),
        "schema_path": str(schema_path),
        "rows": int(len(dataframe)),
        "columns": CANONICAL_AGENT2_COLUMNS,
        "sources": dataframe["source"].value_counts(dropna=False).to_dict()
        if not dataframe.empty
        else {},
    }


def build_agent1_quality_summary(
    *,
    output_dir: Path,
    coverage: dict[str, Any],
    canonical: dict[str, Any],
) -> dict[str, Any]:
    import pandas as pd

    canonical_path = Path(canonical["path"])
    critical_fields = [
        "contract_key_canon",
        "source",
        "buyer_name",
        "publication_date",
        "cpv_codes_raw",
    ]
    quality_columns = [*critical_fields, "supplier_id", "award_date"]
    dataframe = _read_parquet_columns(
        canonical_path,
        quality_columns,
    )
    field_quality = {}
    for field in critical_fields:
        if field not in dataframe.columns or dataframe.empty:
            field_quality[field] = {"missing": None, "coverage_ratio": None}
            continue
        missing = int(
            dataframe[field].isna().sum()
            + (dataframe[field].astype("string").str.strip() == "").sum()
        )
        field_quality[field] = {
            "missing": missing,
            "coverage_ratio": round((len(dataframe) - missing) / len(dataframe), 6)
            if len(dataframe)
            else None,
        }

    total_rows = int(len(dataframe))
    complete_critical_rows = 0
    if total_rows:
        critical_present = dataframe[critical_fields].notna()
        for field in critical_fields:
            critical_present[field] &= dataframe[field].astype("string").str.strip() != ""
        complete_critical_rows = int(critical_present.all(axis=1).sum())

    critical_cells = total_rows * len(critical_fields)
    present_critical_cells = sum(
        total_rows - int(field_quality[field]["missing"] or 0) for field in critical_fields
    )
    completeness = {
        "critical_fields": critical_fields,
        "present_cells": present_critical_cells,
        "total_cells": critical_cells,
        "coverage_ratio": round(present_critical_cells / critical_cells, 6)
        if critical_cells
        else None,
        "complete_rows": complete_critical_rows,
        "complete_rows_ratio": round(complete_critical_rows / total_rows, 6)
        if total_rows
        else None,
        "target_ratio": 0.90,
    }
    completeness["target_met"] = bool(
        completeness["coverage_ratio"] is not None
        and completeness["coverage_ratio"] > completeness["target_ratio"]
    )

    supplier_ids = (
        dataframe["supplier_id"].astype("string").fillna("").str.strip()
        if "supplier_id" in dataframe.columns
        else None
    )
    supplier_ids_present = int((supplier_ids != "").sum()) if supplier_ids is not None else 0
    valid_supplier_ids = (
        sum(_is_valid_spanish_tax_id(value) for value in supplier_ids.tolist())
        if supplier_ids is not None
        else 0
    )
    nif_quality = {
        "valid": valid_supplier_ids,
        "invalid": supplier_ids_present - valid_supplier_ids,
        "missing": total_rows - supplier_ids_present,
        "coverage_ratio": round(supplier_ids_present / total_rows, 6) if total_rows else None,
        "valid_ratio_total": round(valid_supplier_ids / total_rows, 6) if total_rows else None,
        "valid_ratio_present": round(valid_supplier_ids / supplier_ids_present, 6)
        if supplier_ids_present
        else None,
        "target_ratio_total": 0.85,
    }
    nif_quality["target_met"] = bool(
        nif_quality["valid_ratio_total"] is not None
        and nif_quality["valid_ratio_total"] > nif_quality["target_ratio_total"]
    )

    publication_dates = (
        dataframe["publication_date"].astype("string").fillna("").str.strip()
        if "publication_date" in dataframe.columns
        else None
    )
    award_dates = (
        dataframe["award_date"].astype("string").fillna("").str.strip()
        if "award_date" in dataframe.columns
        else None
    )
    comparable_dates = 0
    coherent_dates = 0
    invalid_date_values = 0
    if publication_dates is not None and award_dates is not None and total_rows:
        date_candidates = (publication_dates != "") & (award_dates != "")
        parsed_publication = pd.to_datetime(
            publication_dates.where(date_candidates), errors="coerce", utc=True
        )
        parsed_award = pd.to_datetime(award_dates.where(date_candidates), errors="coerce", utc=True)
        parsed_pairs = date_candidates & parsed_publication.notna() & parsed_award.notna()
        comparable_dates = int(parsed_pairs.sum())
        coherent_dates = int((parsed_pairs & (parsed_publication <= parsed_award)).sum())
        invalid_date_values = int((date_candidates & ~parsed_pairs).sum())

    temporal_quality = {
        "comparable_rows": comparable_dates,
        "coherent_rows": coherent_dates,
        "incoherent_rows": comparable_dates - coherent_dates,
        "invalid_or_unparseable_rows": invalid_date_values,
        "not_evaluable_rows": total_rows - comparable_dates - invalid_date_values,
        "coverage_ratio": round(comparable_dates / total_rows, 6) if total_rows else None,
        "coherence_ratio": round(coherent_dates / comparable_dates, 6)
        if comparable_dates
        else None,
        "target_ratio": 0.98,
    }
    temporal_quality["target_met"] = bool(
        temporal_quality["coherence_ratio"] is not None
        and temporal_quality["coherence_ratio"] > temporal_quality["target_ratio"]
    )

    duplicate_keys = (
        int(dataframe.duplicated(subset=["source", "contract_key_canon"]).sum())
        if not dataframe.empty and {"source", "contract_key_canon"}.issubset(dataframe.columns)
        else 0
    )
    status = "ok"
    if not dataframe.empty and (
        duplicate_keys
        or not completeness["target_met"]
        or not nif_quality["target_met"]
        or not temporal_quality["target_met"]
    ):
        status = "warning"
    if int(canonical.get("rows", 0)) == 0:
        status = "error"

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": status,
        "canonical_rows": int(canonical.get("rows", 0)),
        "coverage": coverage,
        "field_quality": field_quality,
        "quality_metrics": {
            "ocds_critical_completeness": completeness,
            "supplier_tax_id": nif_quality,
            "temporal_coherence": temporal_quality,
        },
        "duplicate_source_contract_keys": duplicate_keys,
        "acceptance_criteria": {
            "agent1_run_report": True,
            "coverage_artifact": Path(coverage["contract_key_coverage_path"]).exists()
            if coverage.get("contract_key_coverage_path")
            else False,
            "canonical_agent2_dataset": canonical_path.exists(),
            "schema_documented": Path(canonical["schema_path"]).exists(),
        },
    }
    path = output_dir / "agent1_data_quality_summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    summary["path"] = str(path)
    return summary


def _is_valid_spanish_tax_id(value: Any) -> bool:
    normalized = re.sub(r"[^A-Z0-9]", "", str(value).upper())
    if re.fullmatch(r"\d{8}[A-Z]", normalized):
        letters = "TRWAGMYFPDXBNJZSQVHLCKE"
        return normalized[-1] == letters[int(normalized[:8]) % 23]
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", normalized):
        letters = "TRWAGMYFPDXBNJZSQVHLCKE"
        number = f"{'XYZ'.index(normalized[0])}{normalized[1:8]}"
        return normalized[-1] == letters[int(number) % 23]
    if not re.fullmatch(r"[ABCDEFGHJKLMNPQRSUVW]\d{7}[0-9A-J]", normalized):
        return False

    initial = normalized[0]
    digits = normalized[1:8]
    even_sum = sum(int(digits[index]) for index in (1, 3, 5))
    odd_sum = sum(
        sum(divmod(int(digits[index]) * 2, 10))
        for index in (0, 2, 4, 6)
    )
    control = (10 - (even_sum + odd_sum) % 10) % 10
    expected_digit = str(control)
    expected_letter = "JABCDEFGHI"[control]
    actual = normalized[-1]
    if initial in "ABEH":
        return actual == expected_digit
    if initial in "KPQS":
        return actual == expected_letter
    return actual in {expected_digit, expected_letter}


CANONICAL_AGENT2_COLUMNS = [
    "contract_key_canon",
    "source",
    "source_record_id",
    "source_notice_id",
    "source_tender_id",
    "source_dataset",
    "buyer_name",
    "buyer_id",
    "supplier_name",
    "supplier_id",
    "contract_title",
    "procedure",
    "publication_date",
    "award_date",
    "estimated_value_eur",
    "awarded_value_eur",
    "cpv_codes_raw",
    "cpv_code_list",
    "source_file",
]


def _canonical_from_boe(dataframe: Any) -> pd.DataFrame:
    import pandas as pd

    if dataframe.empty:
        return pd.DataFrame(columns=CANONICAL_AGENT2_COLUMNS)
    from .boe_units import add_boe_unit_ids

    dataframe = add_boe_unit_ids(dataframe)
    return pd.DataFrame(
        {
            "contract_key_canon": _series_or_empty(dataframe, "id_linea_adjudicacion"),
            "source": "boe",
            "source_record_id": _series_or_empty(dataframe, "id_linea_adjudicacion"),
            "source_notice_id": _series_or_empty(dataframe, "id_aviso"),
            "source_tender_id": _series_or_empty(dataframe, "id_expediente"),
            "source_dataset": "boe_2014_2024",
            "buyer_name": _series_or_empty(dataframe, "buyer_name"),
            "buyer_id": _series_or_empty(dataframe, "institution"),
            "supplier_name": _series_or_empty(dataframe, "supplier_name"),
            "supplier_id": "",
            "contract_title": _series_or_empty(dataframe, "object"),
            "procedure": _series_or_empty(dataframe, "procedure"),
            "publication_date": _series_or_empty(dataframe, "publication_date"),
            "award_date": "",
            "estimated_value_eur": _series_or_empty(dataframe, "estimated_value_eur"),
            "awarded_value_eur": _series_or_empty(dataframe, "awarded_value_eur"),
            "cpv_codes_raw": _series_or_empty(dataframe, "cpv_codes_raw"),
            "cpv_code_list": _series_or_empty(dataframe, "cpv_code_list"),
            "source_file": _series_or_empty(dataframe, "source_file"),
        }
    )


def _canonical_from_place(dataframe: Any) -> pd.DataFrame:
    import pandas as pd

    if dataframe.empty:
        return pd.DataFrame(columns=CANONICAL_AGENT2_COLUMNS)
    return pd.DataFrame(
        {
            "contract_key_canon": _build_contract_keys(
                dataframe,
                source="place",
                id_columns=(
                    "contract_folder_id",
                    "source_dataset",
                    "buyer_name",
                    "buyer_dir3",
                    "published_date",
                ),
            ),
            "source": "place",
            "source_record_id": _series_or_empty(dataframe, "source_entry_id"),
            "source_notice_id": _series_or_empty(dataframe, "source_entry_id"),
            "source_tender_id": _series_or_empty(dataframe, "contract_folder_id"),
            "source_dataset": _series_or_empty(dataframe, "source_dataset"),
            "buyer_name": _series_or_empty(dataframe, "buyer_name"),
            "buyer_id": _series_or_empty(dataframe, "buyer_dir3"),
            "supplier_name": _series_or_empty(dataframe, "winning_party_name"),
            "supplier_id": _series_or_empty(dataframe, "winning_party_nif"),
            "contract_title": _series_or_empty(dataframe, "contract_title"),
            "procedure": _series_or_empty(dataframe, "procedure_code"),
            "publication_date": _series_or_empty(dataframe, "published_date"),
            "award_date": _series_or_empty(dataframe, "award_date"),
            "estimated_value_eur": _series_or_empty(dataframe, "estimated_overall_amount"),
            "awarded_value_eur": _series_or_empty(dataframe, "total_amount"),
            "cpv_codes_raw": _series_or_empty(dataframe, "cpv_codes_raw"),
            "cpv_code_list": _series_or_empty(dataframe, "cpv_code_list"),
            "source_file": _series_or_empty(dataframe, "source_file"),
        }
    )


def _canonical_from_opentender(dataframe: Any) -> pd.DataFrame:
    import pandas as pd

    if dataframe.empty:
        return pd.DataFrame(columns=CANONICAL_AGENT2_COLUMNS)
    return pd.DataFrame(
        {
            "contract_key_canon": _build_contract_keys(
                dataframe,
                source="opentender",
                id_columns=("source_record_id", "source_file", "buyer_name", "publication_date"),
            ),
            "source": "opentender",
            "source_record_id": _series_or_empty(dataframe, "source_record_id"),
            "source_notice_id": _series_or_empty(dataframe, "source_entry_id"),
            "source_tender_id": _series_or_empty(dataframe, "source_record_id"),
            "source_dataset": _series_or_empty(dataframe, "source_file"),
            "buyer_name": _series_or_empty(dataframe, "buyer_name"),
            "buyer_id": _series_or_empty(dataframe, "buyer_id"),
            "supplier_name": _series_or_empty(dataframe, "awarded_supplier_name"),
            "supplier_id": _series_or_empty(dataframe, "awarded_supplier_nif"),
            "contract_title": _series_or_empty(dataframe, "contract_title"),
            "procedure": _series_or_empty(dataframe, "procedure_code"),
            "publication_date": _series_or_empty(dataframe, "publication_date"),
            "award_date": _series_or_empty(dataframe, "award_date"),
            "estimated_value_eur": _series_or_empty(dataframe, "estimated_amount_raw"),
            "awarded_value_eur": _series_or_empty(dataframe, "awarded_amount_raw"),
            "cpv_codes_raw": _series_or_empty(dataframe, "cpv_codes_raw"),
            "cpv_code_list": _series_or_empty(dataframe, "cpv_code_list"),
            "source_file": _series_or_empty(dataframe, "source_file"),
        }
    )


def _series_or_empty(dataframe: Any, column: str) -> Any:
    import pandas as pd

    if column in dataframe.columns:
        return dataframe[column]
    return pd.Series([""] * len(dataframe), index=dataframe.index)


def _agent2_schema() -> dict[str, Any]:
    return {
        "dataset": "agent2_contracts_canonical",
        "description": "Contrato estricto entre Agent1 y Agent2 para scoring/red flags.",
        "primary_key": ["source", "source_record_id", "contract_key_canon"],
        "null_policy": {
            "not_null": [
                "contract_key_canon",
                "source",
                "buyer_name",
                "publication_date",
                "cpv_codes_raw",
            ],
            "nullable": [
                "source_record_id",
                "source_notice_id",
                "source_tender_id",
                "source_dataset",
                "buyer_id",
                "supplier_name",
                "supplier_id",
                "contract_title",
                "procedure",
                "award_date",
                "estimated_value_eur",
                "awarded_value_eur",
                "cpv_code_list",
                "source_file",
            ],
        },
        "columns": {
            "contract_key_canon": "Clave normalizada para cobertura y deduplicacion entre fuentes.",
            "source": "Fuente normalizada: boe, place u opentender.",
            "source_record_id": "Identificador original del registro en la fuente.",
            "source_notice_id": "Identificador del aviso o publicación de origen.",
            "source_tender_id": "Identificador de licitación o expediente dentro de la fuente.",
            "source_dataset": "Dataset o subfuente de procedencia.",
            "buyer_name": "Organismo contratante normalizado por la fuente.",
            "buyer_id": "Identificador de organismo si existe: DIR3, NIF, institucion u otro.",
            "supplier_name": "Adjudicatario/proveedor si existe.",
            "supplier_id": "Identificador fiscal o equivalente del adjudicatario si existe.",
            "contract_title": "Objeto o titulo contractual.",
            "procedure": "Procedimiento contractual normalizado por la fuente.",
            "publication_date": "Fecha de publicacion disponible.",
            "award_date": "Fecha de adjudicacion si existe.",
            "estimated_value_eur": "Valor estimado numerico en euros si existe.",
            "awarded_value_eur": "Valor adjudicado numerico en euros si existe.",
            "cpv_codes_raw": "CPV en formato textual trazable.",
            "cpv_code_list": "Lista de codigos CPV si la fuente la proporciona.",
            "source_file": "Archivo fisico de origen.",
        },
    }


def _build_contract_keys(
    dataframe: Any,
    source: str,
    id_columns: tuple[str, ...],
) -> pd.Series:
    import pandas as pd

    if dataframe.empty or not len(dataframe):
        return pd.Series(dtype="string")

    needed_columns = list(dict.fromkeys((*id_columns, "contract_id", "source_entry_id")))
    id_frame = dataframe[
        [column for column in needed_columns if column in dataframe.columns]
    ].copy()
    for column in id_columns:
        if column not in dataframe.columns:
            id_frame[column] = pd.NA

    if source == "boe":
        file_id = _norm_text(id_frame["file_number"]).fillna("")
        buyer_name = _norm_text(id_frame["buyer_name"]).fillna("")
        date = _norm_date(_norm_text(id_frame["publication_date"])).fillna("")
        primary = file_id + "|" + buyer_name + "|" + date
        fallback = (
            id_frame["contract_id"].astype("string")
            if "contract_id" in id_frame
            else pd.Series("", index=id_frame.index, dtype="string")
        )
        final = _norm_key_candidates(primary, fallback)
    elif source == "place":
        contract_folder_id = _norm_text(id_frame["contract_folder_id"])
        buyer_dir3 = _norm_text(id_frame["buyer_dir3"]).fillna("")
        published_date = _norm_date(_norm_text(id_frame["published_date"])).fillna("")
        key_parts = contract_folder_id + "|" + buyer_dir3 + "|" + published_date
        fallback = _norm_text(id_frame["source_entry_id"]).fillna("")
        final = _norm_key_candidates(key_parts, fallback)
    else:
        record_id = _norm_text(id_frame["source_record_id"])
        buyer_name = _norm_text(id_frame["buyer_name"]).fillna("")
        publication_date = _norm_date(_norm_text(id_frame["publication_date"])).fillna("")
        primary = record_id + "|" + buyer_name + "|" + publication_date
        fallback = _norm_text(id_frame["source_entry_id"]).fillna("")
        final = _norm_key_candidates(primary, fallback)

    return final.str.replace(r"\|{2,}", "|", regex=True).str.strip("|")


def _norm_key_candidates(primary: Any, fallback: Any) -> pd.Series:
    import pandas as pd

    normalized_primary = primary.astype("string").str.strip()
    normalized_fallback = fallback.astype("string").str.strip()
    return normalized_primary.where(normalized_primary != "", normalized_fallback).replace(
        "", pd.NA
    )


def _norm_text_legacy(series: Any) -> pd.Series:

    return (
        series.astype("string")
        .str.upper()
        .str.replace(r"\s+", "", regex=True)
        .str.replace(r"[^A-Z0-9ÁÉÍÓÚÜÑ\-_/]", "", regex=True)
        .str.strip()
    )


def _norm_date(value: Any) -> pd.Series:

    return value.astype("string").fillna("").str.replace(r"\D", "", regex=True).str[:8].fillna("")


def _norm_text(series: Any) -> pd.Series:

    normalized = (
        series.astype("string")
        .fillna("")
        .str.upper()
        .str.replace(r"\s+", "", regex=True)
        .str.strip()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
    )
    return normalized.astype("string").str.replace(r"[^A-Z0-9\\-_/]", "", regex=True)


def _build_universe_rows(
    boe_df: pd.DataFrame,
    place_df: pd.DataFrame,
    op_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    if boe_df.empty and place_df.empty and op_df.empty:
        return []

    boe_set = {
        k: True
        for k in _get_series(boe_df, "contract_key_canon")
        if k is not None and str(k).strip()
    }
    place_set = {
        k: True
        for k in _get_series(place_df, "contract_key_canon")
        if k is not None and str(k).strip()
    }
    op_set = {
        k: True
        for k in _get_series(op_df, "contract_key_canon")
        if k is not None and str(k).strip()
    }
    all_keys = sorted(set(boe_set) | set(place_set) | set(op_set))

    rows: list[dict[str, Any]] = []
    for key in all_keys:
        rows.append(
            {
                "contract_key": key,
                "contract_key_canon": key,
                "present_in_boe": key in boe_set,
                "present_in_place": key in place_set,
                "present_in_opentender": key in op_set,
            }
        )
    return rows


def _build_universe_rows_from_sets(
    boe_keys: set[str],
    place_keys: set[str],
    op_keys: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(boe_keys | place_keys | op_keys):
        rows.append(
            {
                "contract_key": key,
                "contract_key_canon": key,
                "present_in_boe": key in boe_keys,
                "present_in_place": key in place_keys,
                "present_in_opentender": key in op_keys,
            }
        )
    return rows


def _read_parquet_columns(path: Path, columns: list[str]) -> Any:
    import pandas as pd

    if not path.exists():
        return pd.DataFrame()
    try:
        import pyarrow.parquet as pq

        available = set(pq.read_schema(path).names)
        selected = [column for column in columns if column in available]
        return pd.read_parquet(path, columns=selected) if selected else pd.DataFrame()
    except Exception:  # noqa: BLE001 - fallback keeps diagnostics/corrections simple.
        return pd.read_parquet(path)


def _cached_report(path: Path, *, source: str) -> dict[str, Any]:
    if not path.exists():
        return {"source": source, "cached": False}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"source": source, "cached": False, "report_path": str(path)}
    if isinstance(report, dict):
        report["cached"] = True
        report["report_path"] = str(path)
        return report
    return {"source": source, "cached": True, "report_path": str(path)}


def _can_reuse_boe(
    output_dir: Path,
    artifact: dict[str, Any],
    report_path: Path,
    limit: int | None,
    force_rebuild: bool,
) -> bool:
    if force_rebuild or limit is not None:
        return False
    required = [
        output_dir / "contracts_boe.parquet",
        output_dir / "contracts_boe_cpv71.parquet",
        report_path,
    ]
    if not all(path.exists() for path in required):
        return False
    report = _load_json_dict(report_path)
    source = report.get("source") or {}
    return _artifact_matches_source_report(artifact, source)


def _can_reuse_place(
    output_dir: Path,
    artifacts: list[dict[str, Any]],
    report_path: Path,
    limit: int | None,
    force_rebuild: bool,
    place_download: bool,
) -> bool:
    if force_rebuild or place_download or limit is not None:
        return False
    required = [
        output_dir / "contracts_place.parquet",
        output_dir / "contracts_place_cpv71.parquet",
        report_path,
    ]
    if not all(path.exists() for path in required):
        return False
    report = _load_json_dict(report_path)
    report_files = {str(Path(path)) for path in report.get("source_files", [])}
    input_files = {str(Path(str(item.get("path", "")))) for item in artifacts}
    return bool(report_files) and report_files == input_files


def _can_reuse_opentender(
    output_dir: Path,
    artifact: dict[str, Any],
    report_path: Path,
    year: int,
    cpv_prefix: str,
    limit: int | None,
    force_rebuild: bool,
) -> bool:
    if force_rebuild or limit is not None:
        return False
    required = [
        output_dir / f"contracts_opentender_{year}.parquet",
        output_dir / f"contracts_opentender_{year}_cpv{cpv_prefix}.parquet",
        report_path,
    ]
    if not all(path.exists() for path in required):
        return False
    report = _load_json_dict(report_path)
    source = report.get("source") or {}
    return source.get("requested_year") == year and _artifact_matches_source_report(
        artifact, source
    )


def _load_json_dict(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _cleanup_empty_parents(paths: list[Path], *, stop_dir: Path) -> None:
    roots = sorted({path.parent for path in paths}, key=lambda item: len(item.parts), reverse=True)
    for start in roots:
        current = start
        while current != stop_dir.parent:
            try:
                current.rmdir()
            except OSError:
                break
            if current == stop_dir:
                break
            current = current.parent


def _jsonish(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def _get_series(dataframe: pd.DataFrame, column: str) -> pd.Series | None:
    if column not in dataframe.columns:
        return []
    return dataframe[column]


def _artifact_matches_source_report(artifact: dict[str, Any], source: dict[str, Any]) -> bool:
    if not source:
        return False
    if artifact.get("sha256") and source.get("sha256"):
        return source.get("sha256") == artifact.get("sha256")
    if source.get("size_bytes") is not None:
        return source.get("size_bytes") == artifact.get("size_bytes")
    return bool(source.get("sha256"))


def _hydrate_artifact_from_report(artifact: dict[str, Any], report: dict[str, Any]) -> None:
    source = report.get("source") if isinstance(report, dict) else None
    if not isinstance(source, dict):
        return
    if artifact.get("sha256") is None and source.get("sha256"):
        artifact["sha256"] = source["sha256"]
        artifact["fingerprint_mode"] = "cached_report_sha256"


def _input_artifact_metadata(path: Path, *, compute_sha: bool = True) -> dict[str, Any]:
    import hashlib

    digest = None
    if compute_sha:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest() if digest else None,
        "fingerprint_mode": "sha256" if digest else "size_mtime",
        "modified_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ejecuta agente 1 (BOE + PLACE + OpenTender).")
    parser.add_argument(
        "--boe-input",
        type=Path,
        default=Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv"),
    )
    parser.add_argument(
        "--opentender-input", type=Path, default=Path("data/raw/opentender/data-es-ocds-json.zip")
    )
    parser.add_argument("--place-inputs", nargs="*", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--cpv-prefix", default="71")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--place-download", action="store_true")
    parser.add_argument("--place-datasets", nargs="*")
    parser.add_argument("--limit-boe", type=int, default=None)
    parser.add_argument("--limit-place", type=int, default=None)
    parser.add_argument("--limit-opentender", type=int, default=None)
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args(argv)

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
    )

    print("Agent 1 completado")
    print(f"Cobertura: {reports['coverage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
