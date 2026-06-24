from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

BUYER_CATALOG_REQUIRED_COLUMNS = (
    "ID Plataforma",
    "Nombre Órgano Contratación",
    "Ubicación sector público",
    "NIF",
    "DIR3",
)

LEVEL_MAP = {
    "ADMINISTRACION GENERAL DEL ESTADO": "central",
    "COMUNIDADES Y CIUDADES AUTONOMAS": "autonomica",
    "ENTIDADES LOCALES": "local",
}

CODE_COLUMNS = ("DIR3", "NIF", "ID Plataforma")


def enrich_contracts_with_buyer_catalog(
    contracts: Any,
    buyer_catalog_path: Path | None = None,
) -> tuple[Any, dict[str, Any]]:

    if buyer_catalog_path is None:
        return contracts.copy(), {
            "enabled": False,
            "buyer_catalog_path": None,
            "matched_rows": 0,
            "filled_codigo_organismo": 0,
            "filled_nivel_administracion": 0,
            "unmatched_rows": int(len(contracts)),
        }

    buyer_catalog = load_buyer_catalog(buyer_catalog_path)
    return enrich_contracts_with_buyer_catalog_frame(contracts, buyer_catalog, buyer_catalog_path)


def enrich_contracts_with_buyer_catalog_frame(
    contracts: Any,
    buyer_catalog: Any,
    buyer_catalog_path: Path | None = None,
) -> tuple[Any, dict[str, Any]]:

    if contracts.empty:
        return contracts.copy(), {
            "enabled": buyer_catalog_path is not None,
            "buyer_catalog_path": str(buyer_catalog_path) if buyer_catalog_path else None,
            "catalog_rows": int(len(buyer_catalog)),
            "catalog_unique_names": 0,
            "matched_rows": 0,
            "filled_codigo_organismo": 0,
            "filled_nivel_administracion": 0,
            "unmatched_rows": 0,
            "ambiguous_catalog_names": 0,
        }

    index = build_buyer_catalog_index(buyer_catalog)
    enriched = contracts.copy()
    enriched["_buyer_catalog_key"] = _normalize_text_series(enriched, "organismo_contratante")
    merged = enriched.merge(
        index,
        how="left",
        left_on="_buyer_catalog_key",
        right_on="_buyer_catalog_key",
        suffixes=("", "_catalog"),
    )

    existing_code = _string_series(merged, "codigo_organismo")
    existing_level = _string_series(merged, "nivel_administracion")
    catalog_code = _string_series(merged, "codigo_organismo_catalog")
    catalog_level = _string_series(merged, "nivel_administracion_catalog")

    code_fill_mask = _is_blank_series(existing_code) & ~_is_blank_series(catalog_code)
    level_fill_mask = _is_blank_series(existing_level) & ~_is_blank_series(catalog_level)

    merged.loc[code_fill_mask, "codigo_organismo"] = catalog_code.loc[code_fill_mask]
    merged.loc[level_fill_mask, "nivel_administracion"] = catalog_level.loc[level_fill_mask]

    merged["codigo_organismo"] = _nullable_string_series(merged, "codigo_organismo")
    merged["nivel_administracion"] = _nullable_string_series(merged, "nivel_administracion")
    merged = merged.drop(
        columns=[
            "_buyer_catalog_key",
            "codigo_organismo_catalog",
            "nivel_administracion_catalog",
            "buyer_catalog_match_method",
            "buyer_catalog_rows",
        ],
        errors="ignore",
    )

    report = {
        "enabled": True,
        "buyer_catalog_path": str(buyer_catalog_path) if buyer_catalog_path else None,
        "catalog_rows": int(len(buyer_catalog)),
        "catalog_unique_names": int(len(index)),
        "matched_rows": int(
            (~_is_blank_series(catalog_code) | ~_is_blank_series(catalog_level)).sum()
        ),
        "filled_codigo_organismo": int(code_fill_mask.sum()),
        "filled_nivel_administracion": int(level_fill_mask.sum()),
        "rows_with_any_fill": int((code_fill_mask | level_fill_mask).sum()),
        "unmatched_rows": int(
            (
                (merged["codigo_organismo"].astype("string").fillna("").str.strip() == "")
                & (merged["nivel_administracion"].astype("string").fillna("").str.strip() == "")
            ).sum()
        ),
        "ambiguous_catalog_names": int(index["catalog_match_method"].eq("ambiguous").sum())
        if not index.empty
        else 0,
        "match_methods": index["catalog_match_method"].value_counts(dropna=False).to_dict()
        if not index.empty
        else {},
    }
    return merged, report


def build_buyer_catalog_index(buyer_catalog: Any) -> Any:
    import pandas as pd

    if buyer_catalog.empty:
        return pd.DataFrame(
            columns=[
                "_buyer_catalog_key",
                "buyer_catalog_name",
                "codigo_organismo_catalog",
                "nivel_administracion_catalog",
                "catalog_match_method",
                "catalog_rows",
            ]
        )

    required_columns = set(BUYER_CATALOG_REQUIRED_COLUMNS)
    missing = sorted(required_columns - set(buyer_catalog.columns))
    if missing:
        raise ValueError(
            "El catalogo de compradores no contiene las columnas requeridas: " + ", ".join(missing)
        )

    frame = buyer_catalog.copy()
    frame["_buyer_catalog_key"] = _normalize_text_series(frame, "Nombre Órgano Contratación")
    frame = frame[frame["_buyer_catalog_key"] != ""].copy()

    records: list[dict[str, Any]] = []
    for key, group in frame.groupby("_buyer_catalog_key", dropna=False, sort=True):
        if not key:
            continue

        code, method = _choose_code(group)
        level = _choose_level(group)
        records.append(
            {
                "_buyer_catalog_key": key,
                "buyer_catalog_name": _first_non_empty(group["Nombre Órgano Contratación"]),
                "codigo_organismo_catalog": code,
                "nivel_administracion_catalog": level,
                "catalog_match_method": method,
                "catalog_rows": int(len(group)),
            }
        )

    return pd.DataFrame(records)


def load_buyer_catalog(path: Path) -> Any:
    import pandas as pd

    if not path.exists():
        raise FileNotFoundError(f"No existe el catalogo de compradores: {path}")
    return pd.read_excel(path, header=5)


def write_buyer_catalog_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def _choose_code(group: Any) -> tuple[Any, str]:
    import pandas as pd

    for column in CODE_COLUMNS:
        values = _unique_non_empty(group[column])
        if len(values) == 1:
            return values[0], column.lower().replace(" ", "_")
    return pd.NA, "ambiguous"


def _choose_level(group: Any) -> Any:
    import pandas as pd

    values = {
        LEVEL_MAP.get(_normalize_text_key(value))
        for value in group["Ubicación sector público"].dropna().tolist()
    }
    values.discard(None)
    if len(values) == 1:
        return next(iter(values))
    return pd.NA


def _first_non_empty(series: Any) -> Any:
    import pandas as pd

    values = [value for value in series.astype("string").tolist() if value and str(value).strip()]
    return values[0] if values else pd.NA


def _unique_non_empty(series: Any) -> list[str]:
    values = []
    for value in series.astype("string").tolist():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if text not in values:
            values.append(text)
    return values


def _normalize_text_series(dataframe: Any, column: str) -> Any:
    if column not in dataframe.columns:
        import pandas as pd

        return pd.Series([""] * len(dataframe), index=dataframe.index, dtype="string")
    return dataframe[column].astype("string").fillna("").map(_normalize_text_key)


def _normalize_text_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper()).strip()


def _string_series(dataframe: Any, column: str) -> Any:
    import pandas as pd

    if column not in dataframe.columns:
        return pd.Series("", index=dataframe.index, dtype="string")
    return dataframe[column].astype("string").fillna("").str.strip()


def _nullable_string_series(dataframe: Any, column: str) -> Any:
    series = _string_series(dataframe, column)
    return series.mask(series == "")


def _is_blank_series(series: Any) -> Any:
    return series.astype("string").fillna("").str.strip() == ""
