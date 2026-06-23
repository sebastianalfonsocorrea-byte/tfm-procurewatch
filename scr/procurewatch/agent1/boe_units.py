from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_boe_analysis_units_report(
    *,
    boe_cpv71_path: Path,
    award_lines_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    import pandas as pd

    notices = pd.read_parquet(boe_cpv71_path)
    award_lines = pd.read_parquet(award_lines_path)
    award_notices = notices[
        notices["record_type"].astype("string").str.strip().str.casefold().eq("contratación")
    ].copy()

    notices = add_boe_unit_ids(notices)
    award_notices = add_boe_unit_ids(award_notices)
    award_lines = add_boe_unit_ids(award_lines)

    units = {
        "cpv71_notices": _summarize_rows(notices, "id_aviso"),
        "award_notices_any_cpv_position": _summarize_rows(award_notices, "id_aviso"),
        "award_lines_primary_cpv71": _summarize_rows(award_lines, "id_linea_adjudicacion"),
        "award_files_primary_cpv71": _summarize_rows(
            award_lines.drop_duplicates("id_expediente"), "id_expediente"
        ),
    }
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_paths": {
            "boe_cpv71": str(boe_cpv71_path),
            "boe_award_lines_cpv71": str(award_lines_path),
        },
        "definitions": {
            "id_aviso": "Identificador del anuncio BOE; normalmente notice_id.",
            "id_expediente": (
                "Hash estable de organismo normalizado y número de expediente normalizado. "
                "No identifica lotes."
            ),
            "id_linea_adjudicacion": (
                "Hash estable de aviso, expediente, adjudicatario, importe adjudicado, "
                "objeto y CPV. Aproxima una línea/lote cuando BOE no publica id_lote."
            ),
        },
        "units": units,
        "memory_reference": {
            "contracts_awarded": 3443,
            "awarded_amount_eur": 2179000000,
            "buyers": 394,
            "suppliers": 2031,
            "status": "pending_reconciliation",
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "boe_analysis_units_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["path"] = str(report_path)
    return report


def add_boe_unit_ids(dataframe: Any) -> Any:
    import pandas as pd

    result = dataframe.copy()
    result["id_aviso"] = _series(result, "notice_id").combine_first(
        _series(result, "contract_id")
    )
    result["id_expediente"] = [
        _stable_id(
            "expediente",
            _normalize_key(buyer),
            _normalize_key(file_number),
        )
        for buyer, file_number in zip(
            _series(result, "buyer_name"),
            _series(result, "file_number"),
            strict=False,
        )
    ]
    result["id_linea_adjudicacion"] = [
        _stable_id(
            "adjudicacion",
            _normalize_key(notice),
            file_id,
            _normalize_key(supplier),
            _normalize_number(amount),
            _normalize_key(object_text),
            _normalize_key(cpv),
        )
        for notice, file_id, supplier, amount, object_text, cpv in zip(
            result["id_aviso"],
            result["id_expediente"],
            _series(result, "supplier_name"),
            _series(result, "awarded_value_eur"),
            _series(result, "object"),
            _series(result, "cpv_codes_raw"),
            strict=False,
        )
    ]
    return result


def _summarize_rows(dataframe: Any, id_column: str) -> dict[str, Any]:
    amount = dataframe["awarded_value_eur"] if "awarded_value_eur" in dataframe else None
    return {
        "rows": int(len(dataframe)),
        "unique_ids": int(dataframe[id_column].nunique(dropna=True)),
        "buyers_raw": int(dataframe["buyer_name"].nunique(dropna=True))
        if "buyer_name" in dataframe
        else None,
        "buyers_normalized": int(
            dataframe["buyer_name"].map(_normalize_key).replace("", None).nunique(dropna=True)
        )
        if "buyer_name" in dataframe
        else None,
        "suppliers_raw": int(dataframe["supplier_name"].nunique(dropna=True))
        if "supplier_name" in dataframe
        else None,
        "suppliers_normalized": int(
            dataframe["supplier_name"]
            .map(_normalize_key)
            .replace({"": None, "NODISPONIBLE": None})
            .nunique(dropna=True)
        )
        if "supplier_name" in dataframe
        else None,
        "awarded_amount_eur": float(amount.sum(min_count=1))
        if amount is not None and amount.notna().any()
        else None,
    }


def _series(dataframe: Any, column: str) -> Any:
    import pandas as pd

    if column not in dataframe.columns:
        return pd.Series(pd.NA, index=dataframe.index, dtype="string")
    return dataframe[column]


def _normalize_key(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def _normalize_number(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return ""


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera el informe de unidades de análisis BOE.")
    parser.add_argument(
        "--boe-cpv71",
        type=Path,
        default=Path("data/processed/contracts_boe_cpv71.parquet"),
    )
    parser.add_argument(
        "--award-lines",
        type=Path,
        default=Path("data/processed/contracts_boe_award_lines_cpv71.parquet"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args(argv)

    report = build_boe_analysis_units_report(
        boe_cpv71_path=args.boe_cpv71,
        award_lines_path=args.award_lines,
        output_dir=args.output_dir,
    )
    print(f"Informe generado: {report['path']}")
    for unit, metrics in report["units"].items():
        print(f"- {unit}: {metrics['rows']} filas / {metrics['unique_ids']} IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
