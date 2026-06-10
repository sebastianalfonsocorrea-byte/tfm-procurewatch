from __future__ import annotations

from . import pipeline as _pipeline
from .pipeline import (
    build_agent1_quality_summary,
    build_agent2_canonical_dataset,
    build_source_coverage,
    main,
)


def run_agent1(*args, **kwargs):
    _pipeline.build_source_coverage = build_source_coverage
    _pipeline.build_agent2_canonical_dataset = build_agent2_canonical_dataset
    _pipeline.build_agent1_quality_summary = build_agent1_quality_summary
    return _pipeline.run_agent1(*args, **kwargs)


__all__ = [
    "build_agent1_quality_summary",
    "build_agent2_canonical_dataset",
    "build_source_coverage",
    "main",
    "run_agent1",
]
