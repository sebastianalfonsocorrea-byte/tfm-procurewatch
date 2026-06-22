from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from .analytical_schema import CONTRACT_REQUIRED_FIELDS, SUPPLIER_REQUIRED_FIELDS


def build_analytical_datasets(
    *,
    canonical_path: Path,
    output_dir: Path,
    buyer_catalog_path: Path | None = None,
    postgres_dsn: str | None = None,
    write_postgres: bool = False,
) -> dict[str, Any]:
    import pandas as pd

    canonical = pd.read_parquet(canonical_path)
    contracts = map_contracts_to_analytical_schema(canonical)
    buyer_catalog_report = None
    if buyer_catalog_path is not None:
        from .buyer_catalog import enrich_contracts_with_buyer_catalog

        contracts, buyer_catalog_report = enrich_contracts_with_buyer_catalog(
            contracts,
            buyer_catalog_path=buyer_catalog_path,
        )
    suppliers = build_supplier_analytical_table(contracts)

    output_dir.mkdir(parents=True, exist_ok=True)
    contracts_path = output_dir / "contracts_analytical.parquet"
    contracts_preview_path = output_dir / "contracts_analytical_preview.csv"
    suppliers_path = output_dir / "suppliers_analytical.parquet"
    suppliers_preview_path = output_dir / "suppliers_analytical_preview.csv"

    contracts.to_parquet(contracts_path, index=False)
    contracts.head(500).to_csv(contracts_preview_path, index=False, encoding="utf-8")
    suppliers.to_parquet(suppliers_path, index=False)
    suppliers.head(500).to_csv(suppliers_preview_path, index=False, encoding="utf-8")
    if buyer_catalog_report is not None:
        from .buyer_catalog import write_buyer_catalog_report

        write_buyer_catalog_report(
            buyer_catalog_report,
            output_dir / "buyer_catalog_enrichment_report.json",
        )
    postgres_report = None
    if write_postgres:
        if postgres_dsn is None:
            raise ValueError("Se indicó write_postgres=True pero no se proporcionó postgres_dsn.")
        from ..db import write_agent1_analytical_tables_to_postgres

        postgres_report = write_agent1_analytical_tables_to_postgres(
            contracts=contracts,
            suppliers=suppliers,
            postgres_dsn=postgres_dsn,
        )

    return {
        "contracts_path": str(contracts_path),
        "contracts_preview_path": str(contracts_preview_path),
        "contracts_rows": int(len(contracts)),
        "suppliers_path": str(suppliers_path),
        "suppliers_preview_path": str(suppliers_preview_path),
        "suppliers_rows": int(len(suppliers)),
        "buyer_catalog_path": str(buyer_catalog_path) if buyer_catalog_path else None,
        "buyer_catalog_report_path": str(output_dir / "buyer_catalog_enrichment_report.json")
        if buyer_catalog_report is not None
        else None,
        "buyer_catalog_report": buyer_catalog_report,
        "postgres_dsn_configured": postgres_dsn is not None,
        "postgres_write": postgres_report,
    }


def map_contracts_to_analytical_schema(canonical: Any) -> Any:
    import pandas as pd

    result = pd.DataFrame(index=canonical.index)
    result["id_contrato"] = _string_series(canonical, "contract_key_canon")
    result["id_licitacion"] = _nullable_string_series(
        canonical, "source_tender_id"
    ).combine_first(_nullable_string_series(canonical, "source_record_id"))
    result["organismo_contratante"] = _string_series(canonical, "buyer_name")
    sources = _nullable_string_series(canonical, "source")
    buyer_ids = _nullable_string_series(canonical, "buyer_id")
    result["codigo_organismo"] = buyer_ids.mask(sources == "boe")
    result["nivel_administracion"] = pd.Series(pd.NA, index=canonical.index, dtype="string")
    result["tipo_contrato"] = pd.Series(pd.NA, index=canonical.index, dtype="string")
    result["procedimiento"] = _nullable_string_series(canonical, "procedure").map(
        _normalize_procedure
    )

    cpv = _nullable_string_series(canonical, "cpv_codes_raw")
    result["cpv_codigo"] = cpv.map(_extract_cpv_code)
    result["cpv_descripcion"] = cpv.map(_extract_cpv_description)

    result["importe_estimado"] = _numeric_series(canonical, "estimated_value_eur")
    result["importe_adjudicado"] = _numeric_series(canonical, "awarded_value_eur")
    valid_estimate = result["importe_estimado"].notna() & (result["importe_estimado"] != 0)
    result["ratio_desviacion_importe"] = (
        (result["importe_adjudicado"] - result["importe_estimado"])
        / result["importe_estimado"]
    ).where(valid_estimate & result["importe_adjudicado"].notna())

    publication = pd.to_datetime(
        _nullable_string_series(canonical, "publication_date"), errors="coerce"
    )
    award = pd.to_datetime(_nullable_string_series(canonical, "award_date"), errors="coerce")
    result["fecha_publicacion"] = publication.dt.strftime("%Y-%m-%d").astype("string")
    result["fecha_adjudicacion"] = award.dt.strftime("%Y-%m-%d").astype("string")
    result["dias_resolucion"] = (award - publication).dt.days.astype("Int64")
    result.loc[result["dias_resolucion"] < 0, "dias_resolucion"] = pd.NA

    result["numero_ofertas_recibidas"] = pd.Series(
        pd.NA, index=canonical.index, dtype="Int64"
    )
    result["id_adjudicatario"] = _nullable_string_series(canonical, "supplier_id")
    result["nif_adjudicatario"] = _nullable_string_series(canonical, "supplier_id")
    result["nombre_adjudicatario"] = _nullable_string_series(canonical, "supplier_name")

    result["score_red_flags_total"] = pd.Series(
        float("nan"), index=canonical.index, dtype="float64"
    )
    result["red_flags_activados"] = _empty_object_series(canonical.index)
    result["nivel_riesgo"] = pd.Series(pd.NA, index=canonical.index, dtype="string")
    result["score_centralidad_red"] = pd.Series(
        float("nan"), index=canonical.index, dtype="float64"
    )
    result["comunidad_red"] = pd.Series(pd.NA, index=canonical.index, dtype="string")
    result["fragmentos_documentales_recuperados"] = _empty_object_series(canonical.index)

    result["fuentes_cruzadas"] = sources.map(lambda value: [value] if pd.notna(value) else None)
    result["estado_revision"] = pd.Series(
        "pendiente", index=canonical.index, dtype="string"
    )

    return result[list(CONTRACT_REQUIRED_FIELDS)]


def build_supplier_analytical_table(contracts: Any) -> Any:
    import pandas as pd

    supplier_rows = contracts[
        contracts["nombre_adjudicatario"].notna()
        & (contracts["nombre_adjudicatario"].astype("string").str.strip() != "")
    ].copy()
    if supplier_rows.empty:
        return pd.DataFrame(columns=SUPPLIER_REQUIRED_FIELDS)

    supplier_rows["_supplier_name_key"] = supplier_rows["nombre_adjudicatario"].map(
        _normalize_text_key
    )
    supplier_rows["_supplier_nif_key"] = (
        supplier_rows["nif_adjudicatario"].astype("string").fillna("").str.strip().str.upper()
    )
    grouped = supplier_rows.groupby(
        ["_supplier_nif_key", "_supplier_name_key"],
        dropna=False,
        sort=True,
    )

    records: list[dict[str, Any]] = []
    for (nif, _name_key), group in grouped:
        names = group["nombre_adjudicatario"].dropna().astype("string").str.strip()
        records.append(
            {
                "nif": nif or pd.NA,
                "nombre": names.iloc[0] if not names.empty else pd.NA,
                "forma_juridica": pd.NA,
                "sector_actividad": pd.NA,
                "total_contratos": int(group["id_contrato"].nunique()),
                "total_importe_adjudicado": group["importe_adjudicado"].sum(min_count=1),
                "organismos_distintos": int(group["organismo_contratante"].nunique()),
                "procedimientos_menores_ratio": float("nan"),
                "tasa_adjudicacion_licitacion": float("nan"),
                "score_riesgo_agregado": float("nan"),
                "nivel_centralidad_red": float("nan"),
                "comunidades_participacion": None,
                "red_flags_recurrentes": None,
            }
        )

    return pd.DataFrame(records, columns=SUPPLIER_REQUIRED_FIELDS)


def _string_series(dataframe: Any, column: str) -> Any:
    import pandas as pd

    if column not in dataframe.columns:
        return pd.Series("", index=dataframe.index, dtype="string")
    return dataframe[column].astype("string").fillna("").str.strip()


def _nullable_string_series(dataframe: Any, column: str) -> Any:
    series = _string_series(dataframe, column)
    return series.mask(series == "")


def _numeric_series(dataframe: Any, column: str) -> Any:
    import pandas as pd

    if column not in dataframe.columns:
        return pd.Series(float("nan"), index=dataframe.index, dtype="float64")
    return pd.to_numeric(dataframe[column], errors="coerce")


def _empty_object_series(index: Any) -> Any:
    import pandas as pd

    return pd.Series([None] * len(index), index=index, dtype="object")


def _normalize_procedure(value: Any) -> Any:
    import pandas as pd

    if pd.isna(value):
        return pd.NA
    normalized = _normalize_text_key(value)
    if "EMERGENCIA" in normalized:
        return "emergencia"
    if "MENOR" in normalized:
        return "menor"
    if "NEGOCIADO" in normalized:
        return "negociado"
    if "RESTRINGIDO" in normalized:
        return "restringido"
    if "ABIERTO" in normalized:
        return "abierto"
    return pd.NA


def _extract_cpv_code(value: Any) -> Any:
    import pandas as pd

    if pd.isna(value):
        return pd.NA
    match = re.search(r"(?<!\d)(\d{8})(?!\d)", str(value))
    return match.group(1) if match else pd.NA


def _extract_cpv_description(value: Any) -> Any:
    import pandas as pd

    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    match = re.search(r"(?<!\d)\d{8}(?!\d)", text)
    if not match:
        return pd.NA
    description = text[match.end() :].strip(" .,:;()-")
    return description or pd.NA


def _normalize_text_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper()).strip()
