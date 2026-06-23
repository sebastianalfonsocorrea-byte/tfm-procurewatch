from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.types import Date, Float, Integer, String, Text

AGENT1_CONTRACTS_TABLE = "agent1_contracts_analytical"
AGENT1_SUPPLIERS_TABLE = "agent1_suppliers_analytical"
AGENT2_RISK_FLAGS_TABLE = "agent2_risk_flags"
AGENT2_RISK_SCORES_TABLE = "agent2_risk_scores"
AGENT2_SUPPLIER_RISK_TABLE = "agent2_supplier_risk_summary"
AGENT2_MODEL_COMPARISON_TABLE = "agent2_model_comparison"
AGENT2_OUTPUTS_TABLE = "agent2_outputs"


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


def write_agent2_risk_tables_to_postgres(
    *,
    risk_flags: Any,
    risk_scores: Any,
    supplier_risk_summary: Any,
    model_comparison: Any,
    outputs: Any,
    postgres_dsn: str,
    schema: str | None = None,
    if_exists: str = "replace",
) -> dict[str, Any]:
    import pandas as pd

    engine = create_engine(_normalize_postgres_dsn(postgres_dsn), future=True)
    flags_frame = _prepare_agent2_flags_frame(pd.DataFrame(risk_flags))
    scores_frame = _prepare_agent2_scores_frame(pd.DataFrame(risk_scores))
    supplier_frame = _prepare_agent2_supplier_summary_frame(pd.DataFrame(supplier_risk_summary))
    comparison_frame = _prepare_agent2_comparison_frame(pd.DataFrame(model_comparison))
    outputs_frame = _prepare_agent2_outputs_frame(pd.DataFrame(outputs))
    with engine.begin() as connection:
        flags_frame.to_sql(
            AGENT2_RISK_FLAGS_TABLE,
            connection,
            schema=schema,
            if_exists=if_exists,
            index=False,
            dtype=_agent2_flags_dtypes(),
        )
        scores_frame.to_sql(
            AGENT2_RISK_SCORES_TABLE,
            connection,
            schema=schema,
            if_exists=if_exists,
            index=False,
            dtype=_agent2_scores_dtypes(),
        )
        supplier_frame.to_sql(
            AGENT2_SUPPLIER_RISK_TABLE,
            connection,
            schema=schema,
            if_exists=if_exists,
            index=False,
            dtype=_agent2_supplier_dtypes(),
        )
        comparison_frame.to_sql(
            AGENT2_MODEL_COMPARISON_TABLE,
            connection,
            schema=schema,
            if_exists=if_exists,
            index=False,
            dtype=_agent2_comparison_dtypes(),
        )
        outputs_frame.to_sql(
            AGENT2_OUTPUTS_TABLE,
            connection,
            schema=schema,
            if_exists=if_exists,
            index=False,
            dtype=_agent2_outputs_dtypes(),
        )
    engine.dispose()
    return {
        "postgres_dsn": _sanitize_dsn(postgres_dsn),
        "schema": schema,
        "if_exists": if_exists,
        "tables": [
            {
                "name": AGENT2_RISK_FLAGS_TABLE,
                "rows": int(len(flags_frame)),
            },
            {
                "name": AGENT2_RISK_SCORES_TABLE,
                "rows": int(len(scores_frame)),
            },
            {
                "name": AGENT2_SUPPLIER_RISK_TABLE,
                "rows": int(len(supplier_frame)),
            },
            {
                "name": AGENT2_MODEL_COMPARISON_TABLE,
                "rows": int(len(comparison_frame)),
            },
            {
                "name": AGENT2_OUTPUTS_TABLE,
                "rows": int(len(outputs_frame)),
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


def _prepare_agent2_flags_frame(frame: Any) -> Any:
    import pandas as pd

    prepared = frame.copy()
    for column in ("evidence_fields", "evidence_text", "flag_code", "severity", "rule_version"):
        if column in prepared.columns:
            prepared[column] = prepared[column].astype("string")
    for column in ("created_at", "source_snapshot_id", "contract_key_canon", "risk_flag_id"):
        if column in prepared.columns:
            prepared[column] = prepared[column].astype("string")
    if "confidence" in prepared.columns:
        prepared["confidence"] = pd.to_numeric(prepared["confidence"], errors="coerce")
    return prepared


def _prepare_agent2_scores_frame(frame: Any) -> Any:
    import pandas as pd

    prepared = frame.copy()
    for column in ("contract_key_canon", "risk_level", "top_flags", "evaluation_status", "score_version", "source_snapshot_id"):
        if column in prepared.columns:
            prepared[column] = prepared[column].astype("string")
    if "risk_score" in prepared.columns:
        prepared["risk_score"] = pd.to_numeric(prepared["risk_score"], errors="coerce")
    if "flags_count" in prepared.columns:
        prepared["flags_count"] = pd.to_numeric(prepared["flags_count"], errors="coerce")
    return prepared


def _prepare_agent2_supplier_summary_frame(frame: Any) -> Any:
    import pandas as pd

    prepared = frame.copy()
    for column in (
        "supplier_key",
        "supplier_name",
        "supplier_id",
        "score_version",
        "source_snapshot_id",
        "risk_level",
        "red_flags_recurrentes",
    ):
        if column in prepared.columns:
            prepared[column] = prepared[column].astype("string")
    for column in (
        "total_contracts",
        "activated_contracts",
        "organismos_distintos",
        "procedimientos_menores",
    ):
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    for column in ("total_importe_adjudicado", "score_riesgo_agregado", "mean_risk_score", "max_risk_score"):
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared


def _prepare_agent2_outputs_frame(frame: Any) -> Any:
    prepared = frame.copy()
    for column in prepared.columns:
        if column.endswith("_json") or column in {"name", "path", "artifact_path", "artifact_type", "agent_name", "source_snapshot_id", "created_at"}:
            prepared[column] = prepared[column].astype("string")
    return prepared


def _prepare_agent2_comparison_frame(frame: Any) -> Any:
    import pandas as pd

    prepared = frame.copy()
    for column in ("rule_positive", "iforest_anomaly_flag", "pu_label", "agreement_iforest_rule", "agreement_pu_rule"):
        if column in prepared.columns:
            prepared[column] = prepared[column].astype("Int64")
    for column in ("rule_score", "iforest_anomaly_score", "pu_probability"):
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    if "rule_flags_count" in prepared.columns:
        prepared["rule_flags_count"] = pd.to_numeric(prepared["rule_flags_count"], errors="coerce")
    if "contract_key_canon" in prepared.columns:
        prepared["contract_key_canon"] = prepared["contract_key_canon"].astype("string")
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


def _agent2_flags_dtypes() -> dict[str, Any]:
    return {
        "risk_flag_id": String(),
        "contract_key_canon": String(),
        "flag_code": String(),
        "severity": String(),
        "confidence": Float(),
        "evidence_fields": Text(),
        "evidence_text": Text(),
        "rule_version": String(),
        "created_at": String(),
        "source_snapshot_id": String(),
    }


def _agent2_scores_dtypes() -> dict[str, Any]:
    return {
        "contract_key_canon": String(),
        "risk_score": Float(),
        "risk_level": String(),
        "flags_count": Integer(),
        "top_flags": Text(),
        "evaluation_status": String(),
        "score_version": String(),
        "source_snapshot_id": String(),
    }


def _agent2_supplier_dtypes() -> dict[str, Any]:
    return {
        "supplier_key": String(),
        "supplier_id": String(),
        "supplier_name": String(),
        "total_contracts": Integer(),
        "activated_contracts": Integer(),
        "total_importe_adjudicado": Float(),
        "organismos_distintos": Integer(),
        "procedimientos_menores": Integer(),
        "procedimientos_menores_ratio": Float(),
        "mean_risk_score": Float(),
        "max_risk_score": Float(),
        "score_riesgo_agregado": Float(),
        "risk_level": String(),
        "red_flags_recurrentes": Text(),
        "score_version": String(),
        "source_snapshot_id": String(),
    }


def _agent2_comparison_dtypes() -> dict[str, Any]:
    return {
        "contract_key_canon": String(),
        "rule_score": Float(),
        "rule_flags_count": Integer(),
        "rule_positive": Integer(),
        "iforest_anomaly_score": Float(),
        "iforest_anomaly_flag": Integer(),
        "pu_probability": Float(),
        "pu_label": Integer(),
        "agreement_iforest_rule": Integer(),
        "agreement_pu_rule": Integer(),
    }


def _agent2_outputs_dtypes() -> dict[str, Any]:
    return {
        "agent_name": String(),
        "artifact_type": String(),
        "artifact_path": Text(),
        "rows": Integer(),
        "source_snapshot_id": String(),
        "created_at": String(),
        "payload_json": Text(),
    }


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
