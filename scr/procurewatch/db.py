from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.types import Date, Float, Integer, String, Text

AGENT1_CONTRACTS_TABLE = "agent1_contracts_analytical"
AGENT1_SUPPLIERS_TABLE = "agent1_suppliers_analytical"


def write_agent1_analytical_tables_to_postgres(
    *,
    contracts: Any,
    suppliers: Any,
    postgres_dsn: str,
    schema: str | None = None,
    if_exists: str = "replace",
) -> dict[str, Any]:
    import pandas as pd

    engine = create_engine(_normalize_postgres_dsn(postgres_dsn), future=True)
    contract_frame = _prepare_entity_frame(pd.DataFrame(contracts), "contrato")
    supplier_frame = _prepare_entity_frame(pd.DataFrame(suppliers), "adjudicatario")
    with engine.begin() as connection:
        contract_frame.to_sql(
            AGENT1_CONTRACTS_TABLE,
            connection,
            schema=schema,
            if_exists=if_exists,
            index=False,
            dtype=_sqlalchemy_dtypes("contrato"),
        )
        supplier_frame.to_sql(
            AGENT1_SUPPLIERS_TABLE,
            connection,
            schema=schema,
            if_exists=if_exists,
            index=False,
            dtype=_sqlalchemy_dtypes("adjudicatario"),
        )
    engine.dispose()
    return {
        "postgres_dsn": _sanitize_dsn(postgres_dsn),
        "schema": schema,
        "if_exists": if_exists,
        "tables": [
            {
                "name": AGENT1_CONTRACTS_TABLE,
                "rows": int(len(contract_frame)),
            },
            {
                "name": AGENT1_SUPPLIERS_TABLE,
                "rows": int(len(supplier_frame)),
            },
        ],
    }


def _prepare_entity_frame(frame: Any, entity_name: str) -> Any:
    import pandas as pd
    from .agent1.analytical_schema import ANALYTICAL_SCHEMA

    prepared = frame.copy()
    entity_fields = ANALYTICAL_SCHEMA["entities"][entity_name]["fields"]
    for column, spec in entity_fields.items():
        if column not in prepared.columns:
            continue
        column_type = spec["type"]
        if column_type == "date":
            prepared[column] = pd.to_datetime(prepared[column], errors="coerce").dt.date
        elif column_type.startswith("list["):
            prepared[column] = prepared[column].map(_jsonify_list_value)
        elif column_type == "string":
            prepared[column] = prepared[column].astype("string")
    return prepared


def _sqlalchemy_dtypes(entity_name: str) -> dict[str, Any]:
    from .agent1.analytical_schema import ANALYTICAL_SCHEMA

    entity_fields = ANALYTICAL_SCHEMA["entities"][entity_name]["fields"]
    dtypes: dict[str, Any] = {}
    for column, spec in entity_fields.items():
        column_type = spec["type"]
        if column_type == "string":
            dtypes[column] = String()
        elif column_type == "integer":
            dtypes[column] = Integer()
        elif column_type == "float":
            dtypes[column] = Float()
        elif column_type == "date":
            dtypes[column] = Date()
        elif column_type.startswith("list["):
            dtypes[column] = Text()
        else:
            dtypes[column] = Text()
    return dtypes


def _jsonify_list_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if value.__class__.__name__ == "NAType":
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _sanitize_dsn(postgres_dsn: str) -> str:
    if "@" not in postgres_dsn:
        return postgres_dsn
    prefix, suffix = postgres_dsn.split("://", 1) if "://" in postgres_dsn else ("", postgres_dsn)
    if "@" not in suffix:
        return postgres_dsn
    credentials, host_part = suffix.split("@", 1)
    if ":" in credentials:
        username = credentials.split(":", 1)[0]
        return f"{prefix}://{username}:***@{host_part}" if prefix else f"{username}:***@{host_part}"
    return f"{prefix}://***@{host_part}" if prefix else f"***@{host_part}"


def _normalize_postgres_dsn(postgres_dsn: str) -> str:
    if postgres_dsn.startswith("postgresql://"):
        return "postgresql+psycopg://" + postgres_dsn.removeprefix("postgresql://")
    return postgres_dsn
