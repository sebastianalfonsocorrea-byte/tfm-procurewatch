from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import hashlib
import io
import json
import re
import zipfile

import pandas as pd

PARSER_VERSION = "1.0.0"


DEFAULT_INPUT = Path("data/raw/opentender/data-es-ocds-json.zip")
DEFAULT_OUTPUT_DIR = Path("data/processed")


AMOUNT_RE = re.compile(r"[^0-9.,-]")


@dataclass(frozen=True, slots=True)
class OpenTenderRecord:
    source_system: str
    source_year: int | None
    source_file: str
    source_record_id: str
    source_entry_id: str | None
    source_url: str | None
    publication_date: str | None
    updated: str | None
    buyer_id: str | None
    buyer_name: str | None
    buyer_nif: str | None
    buyer_organization_id: str | None
    contract_title: str | None
    procedure_code: str | None
    procurement_category: str | None
    cpv_codes_raw: str
    cpv_code_list: list[str]
    is_cpv_71: bool
    estimated_amount_raw: float | None
    estimated_currency: str | None
    awarded_amount_raw: float | None
    awarded_currency: str | None
    award_date: str | None
    awarded_supplier_name: str | None
    awarded_supplier_id: str | None
    awarded_supplier_nif: str | None
    status: str | None


def normalize_opentender_file(
    input_path: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    year: int | None = None,
    cpv_prefix: str = "71",
    limit: int | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    latest_records: dict[str, OpenTenderRecord] = {}
    errors: list[dict[str, Any]] = []
    total_lines = 0
    parsed_records = 0

    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo ZIP de OpenTender: {input_path}")

    with zipfile.ZipFile(input_path, "r") as zf:
        for entry_name in sorted(_iter_opentender_entries(input_path, year=year)):
            year_str = entry_name.removeprefix("data-es-ocds-").replace(".json", "")
            source_year = int(year_str) if year_str.isdigit() else None
            with zf.open(entry_name, "r") as raw:
                for line_number, raw_line in enumerate(io.TextIOWrapper(raw, encoding="utf-8"), start=1):
                    if limit is not None and total_lines >= limit:
                        break
                    total_lines += 1
                    if not raw_line.strip():
                        continue
                    if cpv_prefix != "all" and not _raw_line_may_contain_cpv_prefix(raw_line, cpv_prefix):
                        continue

                    try:
                        record = parse_opentender_record(
                            json.loads(raw_line),
                            source_year=source_year,
                            source_file=entry_name,
                        )
                        parsed_records += 1
                        if cpv_prefix != "all" and not record.is_cpv_71:
                            continue
                        old_record = latest_records.get(record.source_record_id)
                        if old_record is None or _prefer_newer(old_record.publication_date, record.publication_date):
                            latest_records[record.source_record_id] = record
                    except Exception as exc:  # noqa: BLE001
                        errors.append(
                            {
                                "file": entry_name,
                                "line": line_number,
                                "error": str(exc),
                            }
                        )

            if limit is not None and total_lines >= limit:
                break

    if not latest_records:
        dataframe = pd.DataFrame()
    else:
        dataframe = pd.DataFrame([asdict(row) for row in latest_records.values()])

    cpv_prefix = cpv_prefix or "all"
    suffix = str(year) if year else "all"
    parquet_path = output_dir / f"contracts_opentender_{suffix}.parquet"
    cpv_path = output_dir / f"contracts_opentender_{suffix}_cpv{cpv_prefix}.parquet"
    preview_path = output_dir / f"contracts_opentender_{suffix}_cpv{cpv_prefix}_preview.csv"
    report_path = output_dir / f"contracts_opentender_{suffix}_quality.json"

    if dataframe.empty:
        dataframe.to_parquet(parquet_path, index=False)
        dataframe.to_parquet(cpv_path, index=False)
        dataframe.head(200).to_csv(preview_path, index=False, encoding="utf-8")
    else:
        cpv_dataframe = dataframe[dataframe["is_cpv_71"]].copy()
        dataframe.to_parquet(parquet_path, index=False)
        cpv_dataframe.to_parquet(cpv_path, index=False)
        cpv_dataframe.head(200).to_csv(preview_path, index=False, encoding="utf-8")

    report = _quality_report(
        input_path=input_path,
        parquet_path=parquet_path,
        cpv_path=cpv_path,
        preview_path=preview_path,
        source_year=year,
        dataframe=dataframe,
        total_lines=total_lines,
        errors=errors,
        record_count=parsed_records,
        output_rows=0 if dataframe.empty else int(len(dataframe)),
    )
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def parse_opentender_record(
    payload: dict[str, Any],
    *,
    source_year: int | None,
    source_file: str,
) -> OpenTenderRecord:
    releases = payload.get("releases") or []
    if not releases:
        raise ValueError("registro sin releases")

    release = sorted(
        releases,
        key=lambda item: str(item.get("date", "")),
        reverse=True,
    )[0]

    ocid = release.get("ocid") or payload.get("uri") or "unknown"
    tender = release.get("tender") or {}
    buyer = release.get("buyer") or {}
    buyer_name = buyer.get("name")
    buyer_id = buyer.get("id")
    buyer_nif = extract_identifier(buyer, "TAX_ID") or extract_identifier(buyer, "NIF")
    buyer_organization_id = extract_identifier(buyer, "ORGANIZATION_ID")

    cpv_code_list = extract_cpv_codes_from_items((release.get("items") or []) + (tender.get("items") or []))
    cpv_codes_raw = ", ".join(cpv_code_list)
    is_cpv_71 = any(code.startswith("71") for code in cpv_code_list)

    estimated_value, estimated_currency = parse_amount(
        ((release.get("value") or tender.get("value") or {}) or {}).get("amount"),
        ((release.get("value") or tender.get("value") or {}) or {}).get("currency"),
    )
    award = pick_latest_award(release.get("awards") or [])
    awarded_value, awarded_currency = parse_amount(
        (award.get("value") or {}).get("amount") if isinstance(award, dict) else None,
        (award.get("value") or {}).get("currency") if isinstance(award, dict) else None,
    )

    awarded_supplier_name = None
    awarded_supplier_id = None
    awarded_supplier_nif = None
    award_date = None
    if isinstance(award, dict):
        award_date = award.get("date")
        suppliers = award.get("suppliers") or []
        if suppliers:
            supplier0 = suppliers[0]
            awarded_supplier_name = supplier0.get("name")
            awarded_supplier_id = supplier0.get("id")
            awarded_supplier_nif = extract_identifier(supplier0, "TAX_ID") or extract_identifier(
                supplier0,
                "NIF",
            )

    return OpenTenderRecord(
        source_system="opentender",
        source_year=source_year,
        source_file=source_file,
        source_record_id=release.get("id") or ocid,
        source_entry_id=payload.get("uri"),
        source_url=payload.get("uri"),
        publication_date=release.get("date") or tender.get("datePublished"),
        updated=(payload.get("metaData") or {}).get("lastModified"),
        buyer_id=buyer_id,
        buyer_name=buyer_name,
        buyer_nif=buyer_nif,
        buyer_organization_id=buyer_organization_id,
        contract_title=release.get("title") or tender.get("title"),
        procedure_code=(
            release.get("procurementMethodDetails")
            or release.get("procurementMethod")
            or tender.get("procurementMethodDetails")
            or tender.get("procurementMethod")
        ),
        procurement_category=release.get("mainProcurementCategory") or tender.get("mainProcurementCategory"),
        cpv_codes_raw=cpv_codes_raw,
        cpv_code_list=cpv_code_list,
        is_cpv_71=is_cpv_71,
        estimated_amount_raw=estimated_value,
        estimated_currency=estimated_currency,
        awarded_amount_raw=awarded_value,
        awarded_currency=awarded_currency,
        award_date=award_date,
        awarded_supplier_name=awarded_supplier_name,
        awarded_supplier_id=awarded_supplier_id,
        awarded_supplier_nif=awarded_supplier_nif,
        status=release.get("status") or tender.get("status"),
    )


def deduplicate_records(
    records: list[OpenTenderRecord],
    *,
    cpv_prefix: str,
) -> list[OpenTenderRecord]:
    latest: dict[str, OpenTenderRecord] = {}
    for record in records:
        key = record.source_record_id
        old = latest.get(key)
        if old is None:
            latest[key] = record
            continue

        if _prefer_newer(old.publication_date, record.publication_date):
            latest[key] = record

    if cpv_prefix == "all":
        return list(latest.values())

    return [record for record in latest.values() if record.is_cpv_71]


def pick_latest_award(awards: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not awards:
        return None
    return sorted(
        awards,
        key=lambda item: str(item.get("date", "")),
        reverse=True,
    )[0]


def parse_amount(
    amount: Any,
    currency: str | None,
) -> tuple[float | None, str | None]:
    if amount is None:
        return None, currency
    if isinstance(amount, (int, float)):
        return float(amount), currency
    normalized = AMOUNT_RE.sub("", str(amount).strip())
    if not normalized:
        return None, currency
    try:
        return float(Decimal(normalized.replace(",", "."))), currency
    except InvalidOperation:
        return None, currency


def extract_cpv_codes_from_items(items: list[dict[str, Any]]) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for item in items:
        classification = item.get("classification") or {}
        cpv = str(classification.get("id", "")).strip()
        if cpv and cpv.isdigit() and cpv not in seen:
            seen.add(cpv)
            codes.append(cpv)
    return codes


def extract_identifier(party: dict[str, Any], scheme: str) -> str | None:
    for identifier in party.get("additionalIdentifiers", []) or []:
        if str(identifier.get("scheme") or "").upper() == str(scheme).upper():
            return str(identifier.get("id")).strip()
    return None


def _iter_opentender_entries(input_path: Path, *, year: int | None) -> list[str]:
    with zipfile.ZipFile(input_path, "r") as zf:
        names = [name for name in zf.namelist() if name.startswith("data-es-ocds-") and name.endswith(".json")]
    selected = []
    for name in sorted(names):
        try:
            extracted_year = int(name.replace("data-es-ocds-", "").split(".json")[0][:4])
        except ValueError:
            continue
        if year is None or extracted_year == year or name.endswith("data-es-ocds-year-unavailable.json"):
            selected.append(name)
    return selected


def _raw_line_may_contain_cpv_prefix(raw_line: str, cpv_prefix: str) -> bool:
    prefix = re.escape(str(cpv_prefix))
    return bool(re.search(rf'"id"\s*:\s*"{prefix}\d+', raw_line))


def _prefer_newer(previous: str | None, candidate: str | None) -> bool:
    if candidate is None:
        return False
    if previous is None:
        return True
    return candidate > previous


def _quality_report(
    *,
    input_path: Path,
    parquet_path: Path,
    cpv_path: Path,
    preview_path: Path,
    source_year: int | None,
    dataframe: pd.DataFrame,
    total_lines: int,
    errors: list[dict[str, Any]],
    record_count: int,
    output_rows: int,
) -> dict[str, Any]:
    parsed_rows = 0 if dataframe.empty else int(len(dataframe))
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "path": str(input_path),
            "file_name": input_path.name,
            "size_bytes": input_path.stat().st_size,
            "sha256": sha256_file(input_path),
            "requested_year": source_year,
        },
        "outputs": {
            "contracts_opentender": str(parquet_path),
            "contracts_opentender_cpv": str(cpv_path),
            "preview_csv": str(preview_path),
        },
        "rows": {
            "raw_lines_read": total_lines,
            "parsed_records": record_count,
            "parse_errors": len(errors),
            "output_rows": output_rows,
            "success_rate": round(parsed_rows / total_lines, 6) if total_lines else None,
            "cpv71_rows": int(dataframe["is_cpv_71"].sum()) if not dataframe.empty else 0,
        },
        "error_samples": errors[:20],
        "top_procedure_codes": (
            Counter(filter(None, dataframe["procedure_code"].tolist())).most_common(20)
            if not dataframe.empty
            else {}
        ),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Normaliza descargas OpenTender JSON por lotes (formato OCDS).")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--cpv-prefix", default="71")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    report = normalize_opentender_file(
        input_path=args.input,
        output_dir=args.output_dir,
        year=args.year,
        cpv_prefix=args.cpv_prefix,
        limit=args.limit,
    )

    rows = report["rows"]
    print("Normalizacion OpenTender completada")
    print(f"- Registros parseados: {rows['parsed_records']} / {rows['raw_lines_read']}")
    print(f"- Errores: {rows['parse_errors']}")
    print(f"- Total CPV 71: {rows['cpv71_rows']}")
    print(f"- Output: {report['outputs']['contracts_opentender']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
