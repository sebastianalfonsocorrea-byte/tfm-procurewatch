from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

PARSER_VERSION = "1.0.0"


DEFAULT_OUTPUT_DIR = Path("data/processed")

ATOM_NS = "http://www.w3.org/2005/Atom"
CBC_NS = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
CAC_NS = "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"
CBC_EXT_NS = "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2"
CAC_EXT_NS = "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2"


def _q(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


@dataclass(frozen=True, slots=True)
class PlaceRecord:
    source_dataset: str
    source_file: str
    source_atom: str
    source_entry_id: str | None
    source_kind: str
    detail_url: str | None
    atom_updated: str | None
    published_date: str | None
    contract_folder_id: str | None
    contract_title: str | None
    status_code: str | None
    contract_type_code: str | None
    buyer_name: str | None
    buyer_dir3: str | None
    buyer_nif: str | None
    buyer_platform_id: str | None
    cpv_codes_raw: str
    cpv_code_list: list[str]
    is_cpv_71: bool
    estimated_overall_amount: float | None
    total_amount: float | None
    tax_exclusive_amount: float | None
    procedure_code: str | None
    result_code: str | None
    award_date: str | None
    received_tender_quantity: str | None
    winning_party_name: str | None
    winning_party_nif: str | None


def normalize_place_archives(
    zip_paths: list[Path],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    cpv_prefix: str = "71",
    limit: int | None = None,
    progress_every: int = 10000,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    if not zip_paths:
        raise ValueError("No hay archivos ZIP de PLACE para normalizar.")

    records: list[PlaceRecord] = []
    errors: list[dict[str, Any]] = []
    entries_seen = 0
    deleted_entries = 0

    for zip_path in sorted(zip_paths):
        if not zip_path.exists():
            raise FileNotFoundError(f"No existe el archivo: {zip_path}")

        for record in parse_place_zip(
            zip_path,
            source_dataset=zip_path.parent.name,
            limit=limit,
            cpv_prefix=cpv_prefix,
            progress_every=progress_every,
        ):
            entries_seen += 1
            if record.source_kind == "deleted":
                deleted_entries += 1
                continue
            if cpv_prefix != "all" and not record.is_cpv_71:
                continue
            records.append(record)
            if limit is not None and len(records) >= limit:
                break
        if limit is not None and len(records) >= limit:
            break

    deduped_records = deduplicate_records(records)
    dataframe = pd.DataFrame([asdict(record) for record in deduped_records])
    cpv71_dataframe = dataframe[dataframe["is_cpv_71"]].copy() if not dataframe.empty else dataframe

    parquet_path = output_dir / "contracts_place.parquet"
    cpv_path = output_dir / "contracts_place_cpv71.parquet"
    preview_path = output_dir / "contracts_place_cpv71_preview.csv"
    report_path = output_dir / "contracts_place_quality.json"

    dataframe.to_parquet(parquet_path, index=False)
    cpv71_dataframe.to_parquet(cpv_path, index=False)
    cpv71_dataframe.head(200).to_csv(preview_path, index=False, encoding="utf-8")

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_files": [str(path) for path in zip_paths],
        "outputs": {
            "contracts_place": str(parquet_path),
            "contracts_place_cpv71": str(cpv_path),
            "preview_csv": str(preview_path),
        },
        "rows": {
            "zip_files": len(zip_paths),
            "entries_seen": entries_seen,
            "entries_parsed": len(records) + deleted_entries,
            "entries_deleted": deleted_entries,
            "deduped_rows": int(len(deduped_records)),
            "cpv71_rows": int(len(cpv71_dataframe)),
            "output_rows": int(len(dataframe)),
        },
        "top_procedure_codes": top_counter(dataframe, "procedure_code"),
        "top_buyer_regions": top_counter(dataframe, "buyer_name"),
        "error_samples": errors[:20],
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def parse_place_zip(
    zip_path: Path,
    *,
    source_dataset: str,
    limit: int | None = None,
    cpv_prefix: str = "71",
    progress_every: int = 10000,
) -> list[PlaceRecord]:
    out: list[PlaceRecord] = []
    entries_seen = 0
    candidates_seen = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        atom_files = sorted([name for name in zf.namelist() if name.lower().endswith(".atom")])
        total_atom_files = len(atom_files)
        for atom_index, atom_name in enumerate(atom_files, start=1):
            raw_bytes = zf.read(atom_name)
            for entry_bytes in _iter_atom_entry_chunks(raw_bytes):
                entries_seen += 1
                if cpv_prefix != "all" and not _entry_may_contain_cpv_prefix(
                    entry_bytes, cpv_prefix
                ):
                    if progress_every and entries_seen % progress_every == 0:
                        _print_place_progress(
                            zip_path,
                            atom_index,
                            total_atom_files,
                            entries_seen,
                            candidates_seen,
                            len(out),
                        )
                    continue

                candidates_seen += 1
                try:
                    element = _parse_entry_chunk(entry_bytes)
                except ET.ParseError:
                    continue
                out.append(
                    parse_place_entry(
                        element,
                        source_dataset=source_dataset,
                        source_file=str(zip_path),
                        source_atom=atom_name,
                    )
                )
                if progress_every and entries_seen % progress_every == 0:
                    _print_place_progress(
                        zip_path,
                        atom_index,
                        total_atom_files,
                        entries_seen,
                        candidates_seen,
                        len(out),
                    )
                if limit is not None and len(out) >= limit:
                    _print_place_progress(
                        zip_path,
                        atom_index,
                        total_atom_files,
                        entries_seen,
                        candidates_seen,
                        len(out),
                        final=True,
                    )
                    return out
            if progress_every and atom_index % 25 == 0:
                _print_place_progress(
                    zip_path, atom_index, total_atom_files, entries_seen, candidates_seen, len(out)
                )
    _print_place_progress(
        zip_path,
        total_atom_files,
        total_atom_files,
        entries_seen,
        candidates_seen,
        len(out),
        final=True,
    )
    return out


def _iter_atom_entry_chunks(raw_bytes: bytes):
    cursor = 0
    start_token = b"<entry"
    end_token = b"</entry>"
    while True:
        start = raw_bytes.find(start_token, cursor)
        if start < 0:
            break
        end = raw_bytes.find(end_token, start)
        if end < 0:
            break
        end += len(end_token)
        yield raw_bytes[start:end]
        cursor = end


def _entry_may_contain_cpv_prefix(entry_bytes: bytes, cpv_prefix: str) -> bool:
    prefix = re.escape(str(cpv_prefix)).encode("ascii")
    return bool(
        re.search(rb"<[^>]*ItemClassificationCode[^>]*>\s*" + prefix + rb"\d+", entry_bytes)
    )


def _parse_entry_chunk(entry_bytes: bytes) -> ET.Element:
    wrapped = (
        b'<feed xmlns="http://www.w3.org/2005/Atom" '
        b'xmlns:cbc-place-ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:'
        b'CommonBasicComponents-2" '
        b'xmlns:cbc="urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2" '
        b'xmlns:cac="urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2" '
        b'xmlns:cac-place-ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:'
        b'CommonAggregateComponents-2" '
        b'xmlns:at="http://purl.org/atompub/tombstones/1.0">' + entry_bytes + b"</feed>"
    )
    root = ET.fromstring(wrapped)
    entry = root.find(_q(ATOM_NS, "entry"))
    if entry is None:
        raise ET.ParseError("entry no encontrado tras envolver bloque Atom")
    return entry


def parse_place_entry(
    entry: ET.Element,
    *,
    source_dataset: str,
    source_file: str,
    source_atom: str,
) -> PlaceRecord:
    atom_entry_id = _text(entry.find(_q(ATOM_NS, "id")))
    detail_url = _attr(_first_child(entry.findall(_q(ATOM_NS, "link"))), "href")
    published_date = _text(entry.find(_q(ATOM_NS, "published")))
    updated = _text(entry.find(_q(ATOM_NS, "updated")))

    contract_folder = _extract_contract_scope(entry)
    contract_folder_id = _text(contract_folder.find(_q(CBC_NS, "ContractFolderID")))
    status_node = contract_folder.find(_q(CBC_EXT_NS, "ContractFolderStatusCode"))
    if status_node is None:
        status_node = contract_folder.find(_q(CBC_NS, "ContractFolderStatusCode"))
    status_code = _text(status_node)

    buyer = _first_party(contract_folder)
    buyer_name = (
        _text(buyer.find(f"{_q(CAC_NS, 'PartyName')}/{_q(CBC_NS, 'Name')}"))
        if buyer is not None
        else None
    )
    buyer_dir3 = _find_id_for_scheme(buyer, "DIR3") if buyer is not None else None
    buyer_nif = _find_id_for_scheme(buyer, "NIF") if buyer is not None else None
    buyer_platform_id = _find_id_for_scheme(buyer, "ID_PLATAFORMA") if buyer is not None else None

    project = contract_folder.find(_q(CAC_NS, "ProcurementProject"))
    if project is None:
        project = entry.find(f".//{_q(CAC_NS, 'ProcurementProject')}")

    contract_title = _text(project.find(_q(CBC_NS, "Name"))) if project is not None else None
    contract_type_code = (
        _text(project.find(_q(CBC_NS, "TypeCode"))) if project is not None else None
    )

    cpv_nodes = (
        project.findall(
            f".//{_q(CAC_NS, 'RequiredCommodityClassification')}/"
            f"{_q(CBC_NS, 'ItemClassificationCode')}"
        )
        if project is not None
        else []
    )
    cpv_codes = []
    seen: set[str] = set()
    for node in cpv_nodes:
        code = _text(node)
        if code and code.isdigit() and code not in seen:
            seen.add(code)
            cpv_codes.append(code)

    cpv_codes_raw = ", ".join(cpv_codes)
    is_cpv_71 = any(code.startswith("71") for code in cpv_codes)

    budget_amount = project.find(_q(CAC_NS, "BudgetAmount")) if project is not None else None
    estimated_overall_amount = _parse_amount(
        _text(budget_amount.find(_q(CBC_NS, "EstimatedOverallContractAmount")))
        if budget_amount is not None
        else None
    )
    total_amount = _parse_amount(
        _text(budget_amount.find(_q(CBC_NS, "TotalAmount")) if budget_amount is not None else None)
    )
    tax_exclusive_amount = _parse_amount(
        _text(
            budget_amount.find(_q(CBC_NS, "TaxExclusiveAmount"))
            if budget_amount is not None
            else None
        )
    )

    tendering = (
        contract_folder.find(_q(CAC_NS, "TenderingProcess"))
        if contract_folder is not None
        else None
    )
    procedure_code = (
        _text(tendering.find(_q(CBC_NS, "ProcedureCode"))) if tendering is not None else None
    )

    tender_result = (
        contract_folder.find(_q(CAC_NS, "TenderResult")) if contract_folder is not None else None
    )
    result_code = (
        _text(tender_result.find(_q(CBC_NS, "ResultCode"))) if tender_result is not None else None
    )
    award_date = (
        _text(tender_result.find(_q(CBC_NS, "AwardDate"))) if tender_result is not None else None
    )
    received_tender_quantity = (
        _text(tender_result.find(_q(CBC_NS, "ReceivedTenderQuantity")))
        if tender_result is not None
        else None
    )

    winning_party = (
        tender_result.find(_q(CAC_NS, "WinningParty")) if tender_result is not None else None
    )
    winning_party_name = (
        _text(winning_party.find(f"{_q(CAC_NS, 'PartyName')}/{_q(CBC_NS, 'Name')}"))
        if winning_party is not None
        else None
    )
    winning_party_nif = (
        _find_id_for_scheme(winning_party, "NIF") if winning_party is not None else None
    )

    return PlaceRecord(
        source_dataset=source_dataset,
        source_file=source_file,
        source_atom=source_atom,
        source_entry_id=atom_entry_id,
        source_kind="entry",
        detail_url=detail_url,
        atom_updated=updated,
        published_date=published_date,
        contract_folder_id=contract_folder_id,
        contract_title=contract_title,
        status_code=status_code,
        contract_type_code=contract_type_code,
        buyer_name=buyer_name,
        buyer_dir3=buyer_dir3,
        buyer_nif=buyer_nif,
        buyer_platform_id=buyer_platform_id,
        cpv_codes_raw=cpv_codes_raw,
        cpv_code_list=cpv_codes,
        is_cpv_71=is_cpv_71,
        estimated_overall_amount=estimated_overall_amount,
        total_amount=total_amount,
        tax_exclusive_amount=tax_exclusive_amount,
        procedure_code=procedure_code,
        result_code=result_code,
        award_date=award_date,
        received_tender_quantity=received_tender_quantity,
        winning_party_name=winning_party_name,
        winning_party_nif=winning_party_nif,
    )


def parse_deleted_entry(
    entry: ET.Element,
    source_dataset: str,
    source_atom: str,
    source_file: str,
) -> PlaceRecord:
    return PlaceRecord(
        source_dataset=source_dataset,
        source_file=source_file,
        source_atom=source_atom,
        source_entry_id=entry.get("ref") or entry.get("id") or "unknown",
        source_kind="deleted",
        detail_url=None,
        atom_updated=_text(entry.find(_q(ATOM_NS, "updated"))),
        published_date=None,
        contract_folder_id=None,
        contract_title=None,
        status_code="DELETED",
        contract_type_code=None,
        buyer_name=None,
        buyer_dir3=None,
        buyer_nif=None,
        buyer_platform_id=None,
        cpv_codes_raw="",
        cpv_code_list=[],
        is_cpv_71=False,
        estimated_overall_amount=None,
        total_amount=None,
        tax_exclusive_amount=None,
        procedure_code=None,
        result_code=None,
        award_date=None,
        received_tender_quantity=None,
        winning_party_name=None,
        winning_party_nif=None,
    )


def deduplicate_records(records: list[PlaceRecord]) -> list[PlaceRecord]:
    latest: dict[str, PlaceRecord] = {}
    for record in records:
        key = record.contract_folder_id or record.source_entry_id or "unknown"
        current = latest.get(key)
        if current is None or _compare_timestamp(record.atom_updated, current.atom_updated):
            latest[key] = record
    return list(latest.values())


def _extract_contract_scope(entry: ET.Element) -> ET.Element:
    contract_folder = entry.find(f".//{_q(CAC_EXT_NS, 'ContractFolderStatus')}")
    if contract_folder is not None:
        return contract_folder
    contract_folder = entry.find(f".//{_q(CAC_NS, 'ContractFolderStatus')}")
    return contract_folder if contract_folder is not None else entry


def _compare_timestamp(left: str | None, right: str | None) -> bool:
    if right is None:
        return left is not None
    if left is None:
        return False
    return left > right


def _first_party(contract_folder: ET.Element | None) -> ET.Element | None:
    if contract_folder is None:
        return None
    party = contract_folder.find(
        f".//{_q(CAC_EXT_NS, 'LocatedContractingParty')}/{_q(CAC_NS, 'Party')}"
    )
    if party is not None:
        return party
    return contract_folder.find(f".//{_q(CAC_NS, 'Party')}")


def _find_id_for_scheme(node: ET.Element | None, scheme: str) -> str | None:
    if node is None:
        return None
    for identification in node.findall(
        f".//{_q(CAC_NS, 'PartyIdentification')}/{_q(CBC_NS, 'ID')}"
    ):
        if identification.get("schemeName", "").upper() == scheme.upper():
            return _text(identification)
    return None


def _parse_amount(raw: str | None) -> float | None:
    if not raw:
        return None
    normalized = raw.replace(".", "").replace(",", ".").strip()
    if not normalized:
        return None
    try:
        return float(Decimal(normalized))
    except InvalidOperation:
        return None


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None


def _first_child(nodes: list[ET.Element]) -> ET.Element | None:
    return nodes[0] if nodes else None


def _attr(node: ET.Element | None, attribute: str, default: str | None = None) -> str | None:
    if node is None:
        return default
    return node.attrib.get(attribute, default)


def _local_name(tag: str) -> str:
    return tag.split("}")[-1]


def _print_place_progress(
    zip_path: Path,
    atom_index: int,
    total_atom_files: int,
    entries_seen: int,
    candidates_seen: int,
    output_rows: int,
    *,
    final: bool = False,
) -> None:
    label = "final" if final else "progreso"
    print(
        f"[PLACE {label}] {zip_path.name}: atom {atom_index}/{total_atom_files}, "
        f"entries={entries_seen}, candidatos_cpv={candidates_seen}, output={output_rows}",
        file=sys.stderr,
        flush=True,
    )


def top_counter(dataframe: pd.DataFrame, column: str) -> dict[str, int]:
    if dataframe.empty or column not in dataframe.columns:
        return {}
    return dict(
        Counter(filter(None, dataframe[column].dropna().astype(str).tolist())).most_common(20)
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Normaliza feeds PLACE desde ZIPs Atom/XML.")
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cpv-prefix", default="71")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--progress-every", type=int, default=10000)
    args = parser.parse_args(argv)

    report = normalize_place_archives(
        [*args.inputs],
        output_dir=args.output_dir,
        cpv_prefix=args.cpv_prefix,
        limit=args.limit,
        progress_every=args.progress_every,
    )
    rows = report["rows"]
    print("Normalizacion PLACE completada")
    print(f"- Entradas parseadas: {rows['entries_seen']}")
    print(f"- Registros deduplicados: {rows['deduped_rows']}")
    print(f"- CPV 71: {rows['cpv71_rows']}")
    print(f"- Output: {report['outputs']['contracts_place']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
