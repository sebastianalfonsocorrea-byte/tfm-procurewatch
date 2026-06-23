from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
import hashlib
import gzip
import io
import json
import re
import zipfile
from urllib.parse import urljoin

import requests
import pandas as pd

PARSER_VERSION = "1.3.0"


DEFAULT_INPUT = Path("data/raw/opentender/data-es-ocds-json.zip")
DEFAULT_REGISTRY_PAGE = "https://opentender.eu/es/download"
DEFAULT_REGISTRY_FALLBACK_PAGE = "https://data.open-contracting.org/en/publication/94"
DEFAULT_OUTPUT_DIR = Path("data/processed")
DEFAULT_TIMEOUT_SECONDS = 60
CHUNK_SIZE = 1024 * 1024


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
        raise FileNotFoundError(f"No existe el archivo de OpenTender: {input_path}")

    for entry_name, raw_lines, source_year in _iter_opentender_records(input_path, year=year):
        with raw_lines:
            for line_number, raw_line in enumerate(raw_lines, start=1):
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


def download_opentender_zip(
    *,
    url: str,
    output_path: Path = DEFAULT_INPUT,
    year: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    resolved_url = resolve_opentender_download_url(url, year=year)
    output_path = _download_output_path_for_url(output_path, resolved_url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        return {
            "url": url,
            "resolved_url": resolved_url,
            "output_path": str(output_path),
            "downloaded": False,
            "skipped": True,
            "reason": "exists",
            "size_bytes": output_path.stat().st_size,
            "sha256": sha256_file(output_path),
        }

    temp_path = output_path.with_suffix(f"{output_path.suffix}.tmp" if output_path.suffix else ".tmp")
    try:
        response = requests.get(
            resolved_url,
            stream=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={"User-Agent": "ProcureWatchAnalytics/0.1"},
        )
        response.raise_for_status()
        digest = hashlib.sha256()
        size = 0
        with temp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        _promote_download_temp_file(temp_path, output_path)
        return {
            "url": url,
            "resolved_url": resolved_url,
            "output_path": str(output_path),
            "downloaded": True,
            "skipped": False,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "size_bytes": size,
            "sha256": digest.hexdigest(),
        }
    except requests.RequestException as exc:
        if temp_path.exists():
            _unlink_if_possible(temp_path)
        return {
            "url": url,
            "resolved_url": resolved_url,
            "output_path": str(output_path),
            "downloaded": False,
            "skipped": False,
            "status_code": None,
            "content_type": None,
            "size_bytes": 0,
            "sha256": None,
            "error": str(exc),
        }


def _promote_download_temp_file(temp_path: Path, output_path: Path) -> None:
    try:
        temp_path.replace(output_path)
    except PermissionError:
        output_path.write_bytes(temp_path.read_bytes())
        _unlink_if_possible(temp_path)


def _unlink_if_possible(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return


def _download_output_path_for_url(output_path: Path, resolved_url: str) -> Path:
    resolved_lower = resolved_url.lower()
    if resolved_lower.endswith(".jsonl.gz"):
        if output_path.name.endswith(".jsonl.gz"):
            return output_path
        return output_path.with_suffix("").with_suffix(".jsonl.gz")
    if resolved_lower.endswith(".zip"):
        if output_path.suffix == ".zip":
            return output_path
        return output_path.with_suffix(".zip")
    if resolved_lower.endswith(".gz"):
        if output_path.suffix == ".gz":
            return output_path
        return output_path.with_suffix(".gz")
    return output_path


def resolve_opentender_download_url(url: str, *, year: int | None = None, preferred_format: str = "json") -> str:
    if url.lower().endswith((".zip", ".gz", ".csv", ".json")):
        return url
    if "opentender.eu/es/download" in url:
        try:
            return discover_opentender_download_url(page_url=url, year=year, preferred_format=preferred_format)
        except Exception:  # noqa: BLE001
            return discover_opentender_download_url(
                page_url=DEFAULT_REGISTRY_FALLBACK_PAGE,
                year=year,
                preferred_format=preferred_format,
            )
    if "data.open-contracting.org/en/publication/94" in url:
        return discover_opentender_download_url(page_url=url, year=year, preferred_format=preferred_format)
    return url


def discover_opentender_download_url(
    *,
    page_url: str = DEFAULT_REGISTRY_PAGE,
    year: int | None = None,
    preferred_format: str = "json",
) -> str:
    response = requests.get(
        page_url,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": "ProcureWatchAnalytics/0.1"},
    )
    response.raise_for_status()
    candidates = _extract_links(response.text, base_url=response.url)
    if not candidates:
        raise ValueError(f"No se encontraron enlaces de descarga en {page_url}")

    year_text = str(year) if year is not None else ""
    preferred_suffix = ".jsonl.gz" if preferred_format == "json" else f".{preferred_format}"
    ranked: list[str] = []
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if preferred_suffix in candidate_lower and (not year_text or year_text in candidate_lower):
            ranked.append(candidate)
    if ranked:
        return ranked[0]

    for candidate in candidates:
        candidate_lower = candidate.lower()
        if year_text and year_text in candidate_lower:
            return candidate

    for candidate in candidates:
        if preferred_suffix in candidate.lower():
            return candidate

    return candidates[0]


def parse_opentender_record(
    payload: dict[str, Any],
    *,
    source_year: int | None,
    source_file: str,
) -> OpenTenderRecord:
    release = _normalize_opentender_release(payload)
    if release is None:
        raise ValueError("registro sin datos OCDS normalizables")

    ocid = release.get("ocid") or payload.get("ocid") or payload.get("id") or payload.get("uri") or "unknown"
    tender = release.get("tender") or {}
    buyer = release.get("buyer") or {}
    buyer_name = buyer.get("name")
    buyer_id = buyer.get("id")
    buyer_nif = extract_identifier(buyer, "TAX_ID") or extract_identifier(buyer, "NIF")
    buyer_organization_id = extract_identifier(buyer, "ORGANIZATION_ID")

    cpv_code_list = extract_cpv_codes_from_items(
        (release.get("items") or [])
        + (tender.get("items") or [])
        + extract_cpv_items_from_lots(tender.get("lots") or [])
    )
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
        source_entry_id=payload.get("id") or payload.get("uri") or ocid,
        source_url=payload.get("uri") or payload.get("id"),
        publication_date=release.get("date") or tender.get("datePublished") or (payload.get("metaData") or {}).get("publishedAt"),
        updated=(payload.get("metaData") or {}).get("lastModified") or (payload.get("metaData") or {}).get("lastModifiedDate"),
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


def _normalize_opentender_release(payload: dict[str, Any]) -> dict[str, Any] | None:
    releases = payload.get("releases")
    if releases:
        if not isinstance(releases, list):
            return None
        sorted_releases = sorted(
            (release for release in releases if isinstance(release, dict)),
            key=lambda item: str(item.get("date", "")),
            reverse=True,
        )
        return sorted_releases[0] if sorted_releases else None

    if any(key in payload for key in ("tender", "buyer", "awards", "parties")):
        return payload

    return None


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


def extract_cpv_items_from_lots(lots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for lot in lots:
        if not isinstance(lot, dict):
            continue
        for key in ("items", "item"):
            value = lot.get(key)
            if isinstance(value, list):
                items.extend([entry for entry in value if isinstance(entry, dict)])
            elif isinstance(value, dict):
                items.append(value)
    return items


def extract_identifier(party: dict[str, Any], scheme: str) -> str | None:
    for identifier in party.get("additionalIdentifiers", []) or []:
        if str(identifier.get("scheme") or "").upper() == str(scheme).upper():
            return str(identifier.get("id")).strip()
    return None


def _iter_opentender_records(
    input_path: Path,
    *,
    year: int | None,
):
    suffixes = input_path.suffixes
    if suffixes[-2:] == [".jsonl", ".gz"] or suffixes[-1:] == [".gz"] and input_path.name.endswith(".jsonl.gz"):
        with gzip.open(input_path, "rb") as raw:
            yield input_path.name, io.TextIOWrapper(raw, encoding="utf-8"), year
        return

    if suffixes[-1:] == [".zip"]:
        with zipfile.ZipFile(input_path, "r") as zf:
            for entry_name in sorted(_iter_opentender_entries_from_zip(zf, year=year)):
                extracted_year = _extract_year_from_entry_name(entry_name)
                with zf.open(entry_name, "r") as raw:
                    yield entry_name, io.TextIOWrapper(raw, encoding="utf-8"), extracted_year
        return

    raise ValueError(f"Formato OpenTender no soportado: {input_path}")


def _iter_opentender_entries_from_zip(zf: zipfile.ZipFile, *, year: int | None) -> list[str]:
    names = [name for name in zf.namelist() if name.startswith("data-es-ocds-") and name.endswith(".json")]
    selected = []
    for name in sorted(names):
        extracted_year = _extract_year_from_entry_name(name)
        if extracted_year is None:
            continue
        if year is None or extracted_year == year or name.endswith("data-es-ocds-year-unavailable.json"):
            selected.append(name)
    return selected


def _extract_year_from_entry_name(name: str) -> int | None:
    try:
        extracted = int(name.replace("data-es-ocds-", "").split(".json")[0][:4])
        return extracted
    except ValueError:
        return None


class _HrefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {key: value for key, value in attrs}
        href = attr_map.get("href")
        if href:
            self._current_href = href
            self.links.append((href, ""))

    def handle_data(self, data: str) -> None:
        if self._current_href is None or not self.links:
            return
        href, text = self.links[-1]
        self.links[-1] = (href, f"{text}{data}")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self._current_href = None


def _extract_links(html: str, *, base_url: str) -> list[str]:
    parser = _HrefCollector()
    parser.feed(html)
    links: list[str] = []
    for href, text in parser.links:
        absolute = urljoin(base_url, href)
        if "download" in absolute.lower() or ".jsonl.gz" in absolute.lower() or ".csv.gz" in absolute.lower():
            links.append(absolute)
        elif text and ("2024" in text or "json" in text.lower() or "csv" in text.lower()):
            links.append(absolute)
    seen: set[str] = set()
    unique_links: list[str] = []
    for link in links:
        if link in seen:
            continue
        seen.add(link)
        unique_links.append(link)
    return unique_links


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
