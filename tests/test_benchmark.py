from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from procurewatch.benchmark import run_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_run_benchmark_builds_global_report_from_existing_artifacts(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            processed = root / "processed"
            demo = root / "demo"
            output = root / "benchmark"
            agent4_eval = root / "agent4_evaluation_report.json"
            processed.mkdir()
            demo.mkdir()

            _write_json(processed / "agent1_data_quality_summary.json", _agent1_quality())
            _write_json(
                processed / "agent1_source_coverage_analysis.json",
                _agent1_source_analysis(),
            )
            _write_json(agent4_eval, _agent4_evaluation())
            _write_json(demo / "agent3_graph_report.json", _agent3_report())
            _write_json(
                demo / "agent2_agent3_agent4_demo_report.json",
                _integrated_report(),
            )
            (processed / "agent2_evaluation").mkdir()
            _write_json(
                processed / "agent2_evaluation" / "agent2_evaluation_report.json",
                _agent2_evaluation(),
            )
            (processed / "case_studies").mkdir()
            _write_json(
                processed / "case_studies" / "case_studies_report.json",
                _case_studies_evaluation(),
            )

            report = run_benchmark(
                processed_dir=processed,
                demo_dir=demo,
                output_dir=output,
                agent4_evaluation_path=agent4_eval,
            )

            self.assertEqual(report["status"], "warning")
            self.assertEqual(report["agents"]["agent1"]["status"], "warning")
            self.assertEqual(report["agents"]["agent4"]["status"], "pass")
            sensitivity = next(
                metric
                for metric in report["agents"]["agent2"]["metrics"]
                if metric["metric_id"] == "agent2.threshold_sensitivity.documented"
            )
            self.assertEqual(sensitivity["status"], "pass")
            case_studies = next(
                metric
                for metric in report["agents"]["integrated"]["metrics"]
                if metric["metric_id"] == "integration.case_studies.traceable"
            )
            self.assertEqual(case_studies["status"], "pass")
            self.assertTrue((output / "benchmark_report.json").exists())
            self.assertTrue((output / "benchmark_report.md").exists())
            payload = json.loads((output / "benchmark_report.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"], report["summary"])
            self.assertIn("tfm_context", payload)
            self.assertIn("component_maturity", payload["tfm_context"])
            markdown = (output / "benchmark_report.md").read_text(encoding="utf-8")
            self.assertIn("Lectura en contexto de TFM", markdown)
            self.assertIn("Matriz de alcance del TFM", markdown)
            self.assertIn(
                "Agent2 se mide desde la demo integrada",
                " ".join(payload["limitations"]),
            )

    def test_run_benchmark_fails_when_critical_reports_are_missing(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)

            report = run_benchmark(
                processed_dir=root / "missing_processed",
                demo_dir=root / "missing_demo",
                output_dir=root / "benchmark",
                agent4_evaluation_path=root / "missing_agent4.json",
            )

            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["agents"]["agent1"]["status"], "fail")
            self.assertEqual(report["agents"]["agent4"]["status"], "fail")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _agent1_quality() -> dict[str, object]:
    return {
        "field_quality": {
            "contract_key_canon": {"coverage_ratio": 1.0},
            "source": {"coverage_ratio": 1.0},
            "buyer_name": {"coverage_ratio": 1.0},
            "cpv_codes_raw": {"coverage_ratio": 1.0},
        },
        "duplicate_source_contract_keys": 0,
    }


def _agent1_source_analysis() -> dict[str, object]:
    return {
        "exact_intersections": {
            "boe_place": 0,
            "boe_opentender": 0,
            "place_opentender": 0,
        },
        "candidate_counts": {
            "boe_place": 0,
            "boe_opentender": 0,
            "place_opentender": 2,
        },
    }


def _agent3_report() -> dict[str, object]:
    return {
        "input_rows": 3,
        "nodes_rows": 11,
        "edges_rows": 13,
        "community_count": 2,
        "agent2_features_rows": 3,
        "contracts_without_supplier": 0,
        "contracts_without_cpv": 0,
    }


def _agent4_evaluation() -> dict[str, object]:
    return {
        "summary": {
            "expectation_accuracy": 1.0,
            "average_precision_at_k": 1.0,
            "average_expected_document_recall": 1.0,
            "average_citation_traceability": 1.0,
            "average_contract_key_consistency": 1.0,
            "no_unsupported_fraud_claim_ratio": 1.0,
            "practical_validation_pass_ratio": 1.0,
        },
        "ragas": {
            "status": "not_run",
            "reason": "Corpus pequeno.",
        },
    }


def _integrated_report() -> dict[str, object]:
    return {
        "status": "ready",
        "summary": {
            "agent2_risk_score": 0.5,
            "agent2_red_flags": ["risky_procedure"],
            "agent3_features": 3,
            "agent4_evidences": 2,
            "agent4_citations": 2,
        },
        "validations": [
            {"name": "canonical_exists", "passed": True},
            {"name": "agent4_has_evidence_and_citations", "passed": True},
        ],
        "limitations": ["Demo sintetica y offline."],
    }


def _agent2_evaluation() -> dict[str, object]:
    return {
        "scenarios": {"lower": {}, "base": {}, "upper": {}},
        "comparisons_to_base": {
            "lower": {"score_unchanged_ratio": 0.9},
            "upper": {"score_unchanged_ratio": 0.95},
        },
    }


def _case_studies_evaluation() -> dict[str, object]:
    return {
        "summary": {
            "cases_count": 10,
            "unique_contracts": 10,
            "selection_breakdown": {
                "high_score": 5,
                "medium_risk": 3,
                "control": 2,
            },
            "rule_evidence_coverage_ratio": 1.0,
            "source_traceability_ratio": 1.0,
            "relationships_available_ratio": 1.0,
            "unsupported_fraud_claims": 0,
            "practical_validation_passed": True,
        }
    }


if __name__ == "__main__":
    unittest.main()
