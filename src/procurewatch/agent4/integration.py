from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from procurewatch.agent2 import Agent2Contract, score_contract

from .corpus import DEFAULT_SYNTHETIC_CORPUS_INDEX
from .graph import run_agent4_case_flow
from .qdrant_store import DEFAULT_QDRANT_COLLECTION
from .state import Agent4State

DEFAULT_AGENT2_CANONICAL_PATH = Path("data/processed/agent2_contracts_canonical.parquet")
DEFAULT_AGENT3_FEATURES_PATH = Path("data/processed/agent3_agent2_features.parquet")
DEFAULT_AGENT2_SCORES_PATH = Path("data/processed/agent2_risk_scores.parquet")
DEFAULT_CASE_CONTEXT_OUTPUT_PATH = Path("data/processed/agent4_case_context.json")


def run_agent4_case_context(
    *,
    contract_key_canon: str,
    question: str = "evidencia documental",
    canonical_path: Path = DEFAULT_AGENT2_CANONICAL_PATH,
    agent3_features_path: Path = DEFAULT_AGENT3_FEATURES_PATH,
    agent2_scores_path: Path = DEFAULT_AGENT2_SCORES_PATH,
    corpus_index: Path = DEFAULT_SYNTHETIC_CORPUS_INDEX,
    output_path: Path = DEFAULT_CASE_CONTEXT_OUTPUT_PATH,
    use_services: bool = False,
    qdrant_url: str | None = None,
    collection_name: str = DEFAULT_QDRANT_COLLECTION,
    ollama_base_url: str | None = None,
    embedding_model: str | None = None,
    llm_model: str | None = None,
    chunk_size: int = 900,
    overlap: int = 120,
    retrieval_limit: int = 5,
) -> Agent4State:
    contract_context, warnings = load_contract_context_from_canonical(
        canonical_path=canonical_path,
        contract_key_canon=contract_key_canon,
    )
    agent2_score, agent2_warnings = load_agent2_score_for_contract(
        agent2_scores_path=agent2_scores_path,
        contract_context=contract_context,
    )
    warnings.extend(agent2_warnings)
    agent3_metrics, agent3_warnings = load_agent3_metrics_for_contract(
        agent3_features_path=agent3_features_path,
        contract_key_canon=contract_key_canon,
    )
    warnings.extend(agent3_warnings)

    return run_agent4_case_flow(
        contract_key_canon=contract_key_canon,
        question=question,
        corpus_index=corpus_index,
        output_path=output_path,
        contract_context=contract_context,
        agent2_score=agent2_score,
        agent3_metrics=agent3_metrics,
        warnings=warnings,
        use_services=use_services,
        qdrant_url=qdrant_url,
        collection_name=collection_name,
        ollama_base_url=ollama_base_url,
        embedding_model=embedding_model,
        llm_model=llm_model,
        chunk_size=chunk_size,
        overlap=overlap,
        retrieval_limit=retrieval_limit,
    )


def load_contract_context_from_canonical(
    *,
    canonical_path: Path,
    contract_key_canon: str,
) -> tuple[dict[str, object], list[str]]:
    dataframe = _read_required_parquet(
        canonical_path,
        missing_message=(
            f"No existe canonico Agent2: {canonical_path}. "
            "Ejecuta run-agent1 o usa --canonical-path con un parquet disponible."
        ),
    )
    record, warnings = _select_record_by_contract_key(
        dataframe,
        contract_key_canon=contract_key_canon,
        dataset_name="canonico Agent2",
    )
    return record, warnings


def load_agent2_score_for_contract(
    *,
    agent2_scores_path: Path,
    contract_context: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    """Return the batch Agent2 score so the case file matches the contract ranking.

    RF-03/RF-04 depend on every buyer-supplier pair in the batch, so they only exist in the
    run_agent2 outputs. Without them, fall back to the contract-local score and say so.
    """
    contract_key = _text_value(contract_context, "contract_key_canon")
    local_score = asdict(score_contract(agent2_contract_from_record(contract_context)))
    fallback_warning = (
        f"No hay score de lote Agent2 para {contract_key} en {agent2_scores_path}; se usa el "
        "score local del contrato, que no incluye RF-03/RF-04."
    )
    if not agent2_scores_path.exists():
        return {**local_score, "score_scope": "contract_local"}, [fallback_warning]

    scores = _read_required_parquet(agent2_scores_path, missing_message=fallback_warning)
    try:
        record, warnings = _select_record_by_contract_key(
            scores,
            contract_key_canon=contract_key,
            dataset_name="scores Agent2",
        )
    except ValueError:
        return {**local_score, "score_scope": "contract_local"}, [fallback_warning]

    red_flags = _json_list(record.get("top_flags"))
    flag_texts = _flag_evidence_texts(
        agent2_scores_path.with_name("agent2_risk_flags.parquet"),
        contract_key,
    )
    evidence = dict(local_score["evidence"])
    if flag_texts:
        evidence["flag_evidence_text"] = flag_texts
    return {
        "contract_key_canon": contract_key,
        "risk_score": _float_value(record, "risk_score"),
        "risk_level": _text_value(record, "risk_level"),
        "red_flags": red_flags,
        "data_quality_flags": _json_list(record.get("data_quality_flags")),
        "flags_count": len(red_flags),
        "top_flags": red_flags[:3],
        "evidence": evidence,
        "score_version": _text_value(record, "score_version"),
        "source_snapshot_id": _text_value(record, "source_snapshot_id"),
        "score_scope": "agent2_batch",
    }, warnings


def _flag_evidence_texts(flags_path: Path, contract_key: str) -> dict[str, str]:
    if not flags_path.exists():
        return {}
    import pandas as pd

    columns = ["contract_key_canon", "flag_code", "evidence_text"]
    flags = pd.read_parquet(flags_path, columns=columns)
    matches = flags[flags["contract_key_canon"].astype("string").str.strip() == contract_key]
    return {str(row.flag_code): str(row.evidence_text) for row in matches.itertuples()}


def _json_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def load_agent3_metrics_for_contract(
    *,
    agent3_features_path: Path,
    contract_key_canon: str,
) -> tuple[dict[str, object] | None, list[str]]:
    if not agent3_features_path.exists():
        return None, [
            (
                f"No existe parquet de metricas Agent3: {agent3_features_path}. "
                "Se continua sin metricas relacionales."
            )
        ]

    dataframe = _read_required_parquet(
        agent3_features_path,
        missing_message=f"No existe parquet de metricas Agent3: {agent3_features_path}",
    )
    try:
        record, warnings = _select_record_by_contract_key(
            dataframe,
            contract_key_canon=contract_key_canon,
            dataset_name="features Agent3",
        )
    except ValueError as exc:
        return None, [f"No hay metricas Agent3 para {contract_key_canon}: {exc}"]
    return record, warnings


def agent2_contract_from_record(record: dict[str, object]) -> Agent2Contract:
    return Agent2Contract(
        contract_key_canon=_text_value(record, "contract_key_canon"),
        source=_text_value(record, "source"),
        source_record_id=_text_value(record, "source_record_id"),
        source_dataset=_text_value(record, "source_dataset"),
        buyer_name=_text_value(record, "buyer_name"),
        buyer_id=_text_value(record, "buyer_id"),
        supplier_name=_text_value(record, "supplier_name"),
        supplier_id=_text_value(record, "supplier_id"),
        contract_title=_text_value(record, "contract_title"),
        procedure=_text_value(record, "procedure"),
        publication_date=_text_value(record, "publication_date"),
        award_date=_text_value(record, "award_date"),
        estimated_value_eur=_float_value(record, "estimated_value_eur"),
        awarded_value_eur=_float_value(record, "awarded_value_eur"),
        cpv_codes_raw=_text_value(record, "cpv_codes_raw"),
        cpv_code_list=_text_value(record, "cpv_code_list"),
        source_file=_text_value(record, "source_file"),
    )


def _read_required_parquet(path: Path, *, missing_message: str) -> Any:
    if not path.exists():
        raise FileNotFoundError(missing_message)
    import pandas as pd

    return pd.read_parquet(path)


def _select_record_by_contract_key(
    dataframe: Any,
    *,
    contract_key_canon: str,
    dataset_name: str,
) -> tuple[dict[str, object], list[str]]:
    if "contract_key_canon" not in dataframe.columns:
        raise ValueError(f"El dataset {dataset_name} no contiene contract_key_canon.")

    keys = dataframe["contract_key_canon"].astype("string").str.strip()
    matches = dataframe[keys == contract_key_canon]
    if matches.empty:
        raise ValueError(f"No se encuentra {contract_key_canon} en {dataset_name}.")

    warnings: list[str] = []
    if len(matches) > 1:
        warnings.append(
            f"{dataset_name} contiene {len(matches)} registros para {contract_key_canon}; "
            "se usa el primero ordenado por fuente."
        )
        sort_columns = [column for column in ("source", "source_record_id") if column in matches]
        if sort_columns:
            matches = matches.sort_values(sort_columns, kind="stable")

    return _record_to_json_ready(matches.iloc[0].to_dict()), warnings


def _record_to_json_ready(record: dict[str, object]) -> dict[str, object]:
    return {str(key): _json_ready(value) for key, value in record.items()}


def _json_ready(value: object) -> object:
    if _is_missing(value):
        return None
    if hasattr(value, "item"):
        try:
            return _json_ready(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _text_value(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if value is None:
        return ""
    return str(value)


def _float_value(record: dict[str, object], key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "DEFAULT_AGENT2_CANONICAL_PATH",
    "DEFAULT_AGENT2_SCORES_PATH",
    "DEFAULT_AGENT3_FEATURES_PATH",
    "DEFAULT_CASE_CONTEXT_OUTPUT_PATH",
    "agent2_contract_from_record",
    "load_agent2_score_for_contract",
    "load_agent3_metrics_for_contract",
    "load_contract_context_from_canonical",
    "run_agent4_case_context",
]
