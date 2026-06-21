from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PARSER_VERSION = "1.0.0"

RAW_COLUMNS = [
    "Institucion",
    "Organismo responsable",
    "Expediente",
    "Fecha",
    "Tipo",
    "Naturaleza",
    "Objeto",
    "Procedimiento",
    "Ambito_geografico",
    "Materias_CPV",
    "Codigos_CPV",
    "valor_estimado_licitacion",
    "valor_oferta_adjudicada",
    "nombre_adjudicatario",
    "Enlace HTML",
]

PROCEDURES = {
    "Abierto",
    "Abierto simplificado",
    "Asociación para la innovación",
    "Concurso de proyectos",
    "Diálogo competitivo",
    "Licitación con negociación",
    "Negociado con publicidad",
    "Negociado sin publicidad",
    "No disponible",
    "Normas internas",
    "Restringido",
}

REGIONS = {
    "Andalucía",
    "Aragón",
    "Canarias",
    "Cantabria",
    "Castilla-La Mancha",
    "Castilla y León",
    "Cataluña",
    "Ceuta",
    "Ciudad de Ceuta",
    "Ciudad de Melilla",
    "Comunidad Foral de Navarra",
    "Comunidad de Madrid",
    "Comunidad Valenciana",
    "Comunitat Valenciana",
    "España",
    "Extremadura",
    "Extranjero",
    "Galicia",
    "Illes Balears",
    "La Rioja",
    "Melilla",
    "No disponible",
    "País Vasco",
    "Principado de Asturias",
    "Región de Murcia",
    "Sin definir",
    "Unión Europea",
    "Varias comunidades autónomas",
}

DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")
CPV_RE = re.compile(r"\b\d{8}\b")
NOTICE_ID_RE = re.compile(r"id=([^&#]+)")


class BoeParseError(ValueError):
    """Raised when a BOE raw line cannot be normalized."""


@dataclass(frozen=True, slots=True)
class BoeRecord:
    contract_id: str
    notice_id: str | None
    institution: str
    buyer_name: str
    file_number: str
    publication_date: str | None
    publication_year: int | None
    record_type: str
    contract_nature: str
    object: str
    procedure: str
    region: str
    cpv_subjects: str
    cpv_codes_raw: str
    cpv_code_list: list[str]
    is_cpv_71: bool
    estimated_value_raw: str
    estimated_value_eur: float | None
    awarded_value_raw: str
    awarded_value_eur: float | None
    supplier_name: str
    source_url: str
    source_file: str
    source_line: int
    raw_field_count: int
    repaired_columns: bool
    parser_warning: str | None


def normalize_boe_file(
    input_path: Path,
    output_dir: Path,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    import pandas as pd

    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[BoeRecord] = []
    errors: list[dict[str, Any]] = []
    raw_field_counts: Counter[int] = Counter()
    replacement_lines = 0
    total_data_lines = 0

    with input_path.open("r", encoding="utf-8", errors="replace", newline="") as file:
        header_line = file.readline()
        raw_header = parse_raw_line(header_line)
        if raw_header[: len(RAW_COLUMNS)] != RAW_COLUMNS:
            raise BoeParseError(f"Cabecera inesperada: {raw_header}")

        for line_number, raw_line in enumerate(file, start=2):
            if limit is not None and total_data_lines >= limit:
                break

            total_data_lines += 1
            if "\ufffd" in raw_line:
                replacement_lines += 1

            try:
                raw_fields = parse_raw_line(raw_line)
                raw_field_counts[len(raw_fields)] += 1
                records.append(
                    parse_boe_record(
                        raw_fields,
                        source_file=input_path.name,
                        source_line=line_number,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - parser must keep batch processing alive
                errors.append(
                    {
                        "line": line_number,
                        "error": str(exc),
                        "sample": raw_line[:500],
                    }
                )

    dataframe = records_to_dataframe(records)
    cpv71_dataframe = dataframe[dataframe["is_cpv_71"]].copy() if not dataframe.empty else dataframe

    contracts_path = output_dir / "contracts_boe.parquet"
    cpv71_path = output_dir / "contracts_boe_cpv71.parquet"
    csv_preview_path = output_dir / "contracts_boe_cpv71_preview.csv"
    award_lines_path = output_dir / "contracts_boe_award_lines_cpv71.parquet"
    award_lines_preview_path = output_dir / "contracts_boe_award_lines_cpv71_preview.csv"
    report_path = output_dir / "data_quality_report.json"

    dataframe.to_parquet(contracts_path, index=False)
    cpv71_dataframe.to_parquet(cpv71_path, index=False)
    cpv71_dataframe.head(200).to_csv(csv_preview_path, index=False, encoding="utf-8")
    award_lines = build_boe_award_lines(cpv71_dataframe)
    award_lines.to_parquet(award_lines_path, index=False)
    award_lines.head(200).to_csv(award_lines_preview_path, index=False, encoding="utf-8")

    report = build_quality_report(
        input_path=input_path,
        contracts_path=contracts_path,
        cpv71_path=cpv71_path,
        csv_preview_path=csv_preview_path,
        award_lines_path=award_lines_path,
        award_lines_preview_path=award_lines_preview_path,
        dataframe=dataframe,
        cpv71_dataframe=cpv71_dataframe,
        award_lines_dataframe=award_lines,
        total_data_lines=total_data_lines,
        errors=errors,
        raw_field_counts=raw_field_counts,
        replacement_lines=replacement_lines,
    )
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def build_boe_award_lines(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()

    record_type = dataframe["record_type"].astype("string").str.strip().str.casefold()
    primary_cpv_71 = dataframe["cpv_code_list"].map(_primary_cpv_starts_with_71)
    selected = dataframe[record_type.eq("contratación") & primary_cpv_71].copy()

    deduplication_fields = [
        "notice_id",
        "institution",
        "buyer_name",
        "file_number",
        "object",
        "supplier_name",
        "estimated_value_eur",
        "awarded_value_eur",
        "cpv_codes_raw",
    ]
    available_fields = [
        field for field in deduplication_fields if field in selected.columns
    ]
    if available_fields:
        selected = selected.drop_duplicates(subset=available_fields, keep="first")

    return selected.reset_index(drop=True)


def _primary_cpv_starts_with_71(value: Any) -> bool:
    if value is None:
        return False
    try:
        return len(value) > 0 and str(value[0]).startswith("71")
    except TypeError:
        return False


def parse_raw_line(raw_line: str) -> list[str]:
    clean = raw_line.rstrip("\r\n").rstrip(";")
    if clean.startswith('"') and clean.endswith('"'):
        clean = clean[1:-1]
    clean = clean.replace('""', '"')
    return [normalize_text(value) for value in next(csv.reader([clean]))]


def parse_boe_record(
    fields: list[str],
    *,
    source_file: str,
    source_line: int,
) -> BoeRecord:
    date_index = find_date_index(fields)
    if date_index < 3:
        raise BoeParseError("No hay suficientes campos antes de la fecha")

    url_index = find_url_index(fields)
    if url_index <= date_index:
        raise BoeParseError("No se encontro URL de fuente tras la fecha")

    institution, buyer_name, file_number = split_pre_date_fields(fields[:date_index])

    publication_date = parse_date(fields[date_index])
    publication_year = int(publication_date[:4]) if publication_date else None
    record_type = require_field(fields, date_index + 1, "tipo")
    contract_nature = require_field(fields, date_index + 2, "naturaleza")

    procedure_index = find_procedure_index(fields, date_index + 3, url_index)
    if procedure_index is None:
        raise BoeParseError("No se encontro procedimiento reconocible")

    region_index = procedure_index + 1
    procedure = normalize_text(fields[procedure_index])
    region = normalize_text(fields[region_index])
    object_text = join_parts(fields[date_index + 3 : procedure_index])
    source_url = normalize_text(fields[url_index])

    tail = repair_split_euro_tokens(fields[region_index + 1 : url_index])
    estimated_idx, awarded_idx = find_value_pair(tail)
    cpv_parts = tail[:estimated_idx]
    supplier_parts = tail[awarded_idx + 1 :]
    if not cpv_parts:
        raise BoeParseError("No se encontraron campos CPV")
    if not supplier_parts:
        raise BoeParseError("No se encontro adjudicatario")

    cpv_subjects = normalize_text(cpv_parts[0])
    cpv_codes_raw = join_parts(cpv_parts[1:]) if len(cpv_parts) > 1 else cpv_subjects
    cpv_text = join_parts(cpv_parts)
    cpv_code_list = extract_cpv_codes(cpv_text)
    estimated_value_raw = normalize_text(tail[estimated_idx])
    awarded_value_raw = normalize_text(tail[awarded_idx])
    supplier_name = join_parts(supplier_parts)
    notice_id = extract_notice_id(source_url)
    contract_id = notice_id or f"{file_number}|{publication_date or 'unknown'}|{source_line}"
    raw_field_count = len(fields)

    warnings = []
    if raw_field_count != len(RAW_COLUMNS):
        warnings.append(f"reparada_desde_{raw_field_count}_campos")
    if "\ufffd" in " ".join(fields):
        warnings.append("caracteres_reemplazados_por_codificacion")

    return BoeRecord(
        contract_id=contract_id,
        notice_id=notice_id,
        institution=institution,
        buyer_name=buyer_name,
        file_number=file_number,
        publication_date=publication_date,
        publication_year=publication_year,
        record_type=record_type,
        contract_nature=contract_nature,
        object=object_text,
        procedure=procedure,
        region=region,
        cpv_subjects=cpv_subjects,
        cpv_codes_raw=cpv_codes_raw,
        cpv_code_list=cpv_code_list,
        is_cpv_71=any(code.startswith("71") for code in cpv_code_list),
        estimated_value_raw=estimated_value_raw,
        estimated_value_eur=parse_eur(estimated_value_raw),
        awarded_value_raw=awarded_value_raw,
        awarded_value_eur=parse_eur(awarded_value_raw),
        supplier_name=supplier_name,
        source_url=source_url,
        source_file=source_file,
        source_line=source_line,
        raw_field_count=raw_field_count,
        repaired_columns=raw_field_count != len(RAW_COLUMNS),
        parser_warning=";".join(warnings) if warnings else None,
    )


def find_date_index(fields: list[str]) -> int:
    for index, field in enumerate(fields):
        if DATE_RE.fullmatch(field):
            return index
    raise BoeParseError("No se encontro fecha dd/mm/yyyy")


def split_pre_date_fields(fields: list[str]) -> tuple[str, str, str]:
    if len(fields) < 3:
        raise BoeParseError("No hay suficientes campos antes de la fecha")

    file_number = normalize_text(fields[-1])
    left = fields[:-1]
    buyer_start = len(left) - 1
    for index in range(1, len(left)):
        if looks_like_buyer_start(left[index]):
            buyer_start = index
            break

    institution = join_parts(left[:buyer_start])
    buyer_name = join_parts(left[buyer_start:])
    if not institution:
        institution = normalize_text(left[0])
        buyer_name = join_parts(left[1:])

    return institution, buyer_name, file_number


def looks_like_buyer_start(value: str) -> bool:
    normalized = normalize_text(value)
    return any(character.islower() for character in normalized)


def find_url_index(fields: list[str]) -> int:
    for index in range(len(fields) - 1, -1, -1):
        field = fields[index]
        if field.startswith("http://") or field.startswith("https://"):
            return index
    raise BoeParseError("No se encontro URL http/https")


def find_procedure_index(fields: list[str], start: int, stop: int) -> int | None:
    for index in range(start, stop - 1):
        if fields[index] in PROCEDURES and is_region_value(fields[index + 1]) and stop - index >= 6:
            return index

    for index in range(start, stop):
        if fields[index] in PROCEDURES and fields[index] != "No disponible" and stop - index >= 6:
            return index

    return None


def is_region_value(value: str) -> bool:
    normalized = normalize_text(value)
    if normalized in REGIONS:
        return True
    return any(normalize_text(part) in REGIONS for part in normalized.split(","))


def find_value_pair(tail: list[str]) -> tuple[int, int]:
    for index in range(len(tail) - 3, -1, -1):
        if is_value_field(tail[index]) and is_value_field(tail[index + 1]):
            return index, index + 1
    raise BoeParseError("No se encontro pareja importe estimado/adjudicado")


def repair_split_euro_tokens(parts: list[str]) -> list[str]:
    repaired: list[str] = []
    index = 0
    while index < len(parts):
        current = normalize_text(parts[index])
        next_value = normalize_text(parts[index + 1]) if index + 1 < len(parts) else ""
        if looks_like_amount_integer_part(current) and looks_like_amount_decimal_part(next_value):
            repaired.append(f"{current},{next_value}")
            index += 2
            continue

        repaired.append(current)
        index += 1

    return repaired


def looks_like_amount_integer_part(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}(?:\.\d{3})*|\d+", normalize_text(value)))


def looks_like_amount_decimal_part(value: str) -> bool:
    return bool(re.fullmatch(r"\d{2}\s+euros?", normalize_text(value).lower()))


def is_value_field(value: str) -> bool:
    normalized = normalize_text(value).lower()
    return normalized == "no disponible" or "euro" in normalized or bool(
        re.search(r"\d[\d.]*,\d{2}", normalized)
    )


def parse_date(value: str) -> str | None:
    normalized = normalize_text(value)
    if not normalized or normalized.lower() == "no disponible":
        return None
    return datetime.strptime(normalized, "%d/%m/%Y").date().isoformat()


def parse_eur(value: str) -> float | None:
    normalized = normalize_text(value).lower()
    if not normalized or normalized == "no disponible":
        return None

    candidate = (
        normalized.replace("euros", "")
        .replace("euro", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )
    candidate = re.sub(r"[^0-9.\-]", "", candidate)
    if not candidate:
        return None

    try:
        return float(Decimal(candidate))
    except InvalidOperation as exc:
        raise BoeParseError(f"Importe no parseable: {value}") from exc


def extract_cpv_codes(value: str) -> list[str]:
    seen: set[str] = set()
    codes = []
    for code in CPV_RE.findall(value):
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def extract_notice_id(url: str) -> str | None:
    match = NOTICE_ID_RE.search(url)
    return match.group(1) if match else None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip('"')).strip()


def join_parts(parts: list[str]) -> str:
    return normalize_text(", ".join(part for part in parts if normalize_text(part)))


def require_field(fields: list[str], index: int, name: str) -> str:
    try:
        value = normalize_text(fields[index])
    except IndexError as exc:
        raise BoeParseError(f"Campo obligatorio ausente: {name}") from exc
    if not value:
        raise BoeParseError(f"Campo obligatorio vacio: {name}")
    return value


def records_to_dataframe(records: list[BoeRecord]) -> pd.DataFrame:
    import pandas as pd

    dataframe = pd.DataFrame([asdict(record) for record in records])
    if dataframe.empty:
        return dataframe

    dataframe["publication_date"] = pd.to_datetime(dataframe["publication_date"], errors="coerce")
    return dataframe


def build_quality_report(
    *,
    input_path: Path,
    contracts_path: Path,
    cpv71_path: Path,
    csv_preview_path: Path,
    award_lines_path: Path,
    award_lines_preview_path: Path,
    dataframe: pd.DataFrame,
    cpv71_dataframe: pd.DataFrame,
    award_lines_dataframe: pd.DataFrame,
    total_data_lines: int,
    errors: list[dict[str, Any]],
    raw_field_counts: Counter[int],
    replacement_lines: int,
) -> dict[str, Any]:
    import pandas as pd

    parsed_rows = int(len(dataframe))
    missing = (
        {
            column: int(dataframe[column].isna().sum() + (dataframe[column] == "").sum())
            for column in dataframe.columns
            if dataframe[column].dtype == "object"
        }
        if not dataframe.empty
        else {}
    )

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "path": str(input_path),
            "file_name": input_path.name,
            "size_bytes": input_path.stat().st_size,
            "sha256": sha256_file(input_path),
        },
        "outputs": {
            "contracts_boe": str(contracts_path),
            "contracts_boe_cpv71": str(cpv71_path),
            "cpv71_preview_csv": str(csv_preview_path),
            "contracts_boe_award_lines_cpv71": str(award_lines_path),
            "award_lines_cpv71_preview_csv": str(award_lines_preview_path),
        },
        "rows": {
            "total_data_lines": total_data_lines,
            "parsed_rows": parsed_rows,
            "parse_errors": len(errors),
            "parse_success_rate": round(parsed_rows / total_data_lines, 6)
            if total_data_lines
            else None,
            "cpv71_rows": int(len(cpv71_dataframe)),
            "cpv71_award_lines": int(len(award_lines_dataframe)),
            "cpv71_award_lines_before_exact_deduplication": int(
                (
                    cpv71_dataframe["record_type"]
                    .astype("string")
                    .str.strip()
                    .str.casefold()
                    .eq("contratación")
                    & cpv71_dataframe["cpv_code_list"].map(_primary_cpv_starts_with_71)
                ).sum()
            )
            if not cpv71_dataframe.empty
            else 0,
            "repaired_rows": int(dataframe["repaired_columns"].sum()) if not dataframe.empty else 0,
            "lines_with_replacement_char": replacement_lines,
        },
        "raw_field_counts": {str(key): value for key, value in raw_field_counts.items()},
        "top_procedures": counter_from_series(dataframe, "procedure"),
        "top_contract_natures": counter_from_series(dataframe, "contract_nature"),
        "rows_by_year": counter_from_series(dataframe, "publication_year"),
        "missing_values": missing,
        "error_samples": errors[:20],
    }


def counter_from_series(dataframe, column: str, *, limit: int = 20) -> dict[str, int]:
    import pandas as pd

    if dataframe.empty or column not in dataframe:
        return {}
    counter = Counter(str(value) for value in dataframe[column].dropna().tolist())
    return dict(counter.most_common(limit))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normaliza el CSV BOE 2014-2024.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv"),
        help="Ruta del CSV raw.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directorio para Parquet y reporte.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limite opcional de filas raw.")
    args = parser.parse_args(argv)

    report = normalize_boe_file(args.input, args.output_dir, limit=args.limit)
    rows = report["rows"]
    print("Normalizacion BOE completada")
    print(f"- Filas parseadas: {rows['parsed_rows']} / {rows['total_data_lines']}")
    print(f"- Errores de parseo: {rows['parse_errors']}")
    print(f"- Filas CPV 71: {rows['cpv71_rows']}")
    print(f"- Dataset: {report['outputs']['contracts_boe']}")
    print(f"- Dataset CPV 71: {report['outputs']['contracts_boe_cpv71']}")
    print("- Reporte: data/processed/data_quality_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
