from __future__ import annotations

from ..db import write_agent1_analytical_tables_to_postgres
from . import pipeline as _pipeline
from .analytical_dataset import (
    build_analytical_datasets,
    build_supplier_analytical_table,
    map_contracts_to_analytical_schema,
)
from .analytical_schema import (
    ANALYTICAL_SCHEMA,
    CONTRACT_REQUIRED_FIELDS,
    CONTRACT_SCHEMA,
    SUPPLIER_REQUIRED_FIELDS,
    SUPPLIER_SCHEMA,
)
from .buyer_catalog import enrich_contracts_with_buyer_catalog
from .coverage_report import build_agent1_coverage_report
from .pipeline import (
    build_agent1_quality_summary,
    build_agent2_canonical_dataset,
    build_source_coverage,
    main,
)
from .source_diagnostics import build_agent1_source_coverage_analysis


def run_agent1(*args, **kwargs):
    _pipeline.build_source_coverage = build_source_coverage
    _pipeline.build_agent2_canonical_dataset = build_agent2_canonical_dataset
    _pipeline.build_agent1_quality_summary = build_agent1_quality_summary
    return _pipeline.run_agent1(*args, **kwargs)


__all__ = [
    "ANALYTICAL_SCHEMA",
    "CONTRACT_REQUIRED_FIELDS",
    "CONTRACT_SCHEMA",
    "SUPPLIER_REQUIRED_FIELDS",
    "SUPPLIER_SCHEMA",
    "build_analytical_datasets",
    "build_agent1_coverage_report",
    "build_agent1_quality_summary",
    "build_agent2_canonical_dataset",
    "build_agent1_source_coverage_analysis",
    "build_source_coverage",
    "build_supplier_analytical_table",
    "enrich_contracts_with_buyer_catalog",
    "main",
    "map_contracts_to_analytical_schema",
    "run_agent1",
    "write_agent1_analytical_tables_to_postgres",
]
