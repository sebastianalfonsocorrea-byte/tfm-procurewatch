from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from procurewatch.benchmark import run_case_study_evaluation, select_case_studies


class CaseStudyTests(unittest.TestCase):
    def test_case_study_evaluation_builds_ten_traceable_files(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            canonical_path = root / "canonical.parquet"
            scores_path = root / "scores.parquet"
            flags_path = root / "flags.parquet"
            features_path = root / "features.parquet"
            corpus_path = root / "corpus.json"
            output_dir = root / "case_studies"
            canonical, scores, flags, features = _case_study_frames()
            canonical.to_parquet(canonical_path, index=False)
            scores.to_parquet(scores_path, index=False)
            flags.to_parquet(flags_path, index=False)
            features.to_parquet(features_path, index=False)
            corpus_path.write_text(
                json.dumps({"corpus_id": "empty-test", "documents": []}),
                encoding="utf-8",
            )

            report = run_case_study_evaluation(
                canonical_path=canonical_path,
                scores_path=scores_path,
                flags_path=flags_path,
                agent3_features_path=features_path,
                corpus_index_path=corpus_path,
                output_dir=output_dir,
            )

            summary = report["summary"]
            self.assertEqual(summary["cases_count"], 10)
            self.assertEqual(summary["unique_contracts"], 10)
            self.assertEqual(
                summary["selection_breakdown"],
                {"high_score": 5, "medium_risk": 3, "control": 2},
            )
            self.assertEqual(summary["rule_evidence_coverage_ratio"], 1.0)
            self.assertEqual(summary["relationships_available_ratio"], 1.0)
            self.assertEqual(summary["documentary_evidence_case_ratio"], 0.0)
            self.assertTrue(summary["practical_validation_passed"])
            selected_sources = {
                case["contract"]["source"]
                for case in report["cases"]
                if case["selection"]["group"] == "medium_risk"
            }
            self.assertEqual(selected_sources, {"place", "boe", "opentender"})
            controls = [
                case for case in report["cases"] if case["selection"]["group"] == "control"
            ]
            self.assertTrue(all(case["risk"]["risk_score"] == 0 for case in controls))
            self.assertTrue(all(not case["risk"]["active_rules"] for case in controls))
            self.assertTrue(
                all(
                    "No hay evidencia documental recuperada" in " ".join(case["warnings"])
                    for case in report["cases"]
                )
            )
            self.assertTrue((output_dir / "case_studies_report.json").exists())
            self.assertTrue((output_dir / "case_studies_report.md").exists())
            for position in range(1, 11):
                self.assertTrue((output_dir / "cases" / f"CS-{position:02d}.json").exists())
                self.assertTrue((output_dir / "cases" / f"CS-{position:02d}.md").exists())

    def test_case_selection_rejects_insufficient_medium_candidates(self) -> None:
        _, scores, _, _ = _case_study_frames()
        limited = scores[~scores["source_hint"].isin({"medium-2", "medium-3"})].copy()
        limited["source"] = limited["source_hint"].map(_source_for_hint)
        limited["buyer_name"] = limited["contract_key_canon"].map(lambda key: f"Buyer {key}")
        limited["supplier_name"] = limited["contract_key_canon"].map(
            lambda key: f"Supplier {key}"
        )

        with self.assertRaisesRegex(ValueError, "tres contratos de riesgo medio"):
            select_case_studies(limited)


def _case_study_frames():
    import pandas as pd

    records: list[dict[str, object]] = []
    score_records: list[dict[str, object]] = []
    flag_records: list[dict[str, object]] = []
    feature_records: list[dict[str, object]] = []
    definitions = [
        *(f"high-{index}" for index in range(1, 7)),
        "medium-1",
        "medium-2",
        "medium-3",
        "control-place",
        "control-boe",
        "control-opentender",
    ]
    for index, hint in enumerate(definitions, start=1):
        source = _source_for_hint(hint)
        if hint.startswith("high"):
            score, level, rules = 65.0, "alto", ["RF-03"]
        elif hint.startswith("medium"):
            score = 45.0 if hint != "medium-3" else 40.0
            level, rules = "medio", ["RF-02"]
        else:
            score, level, rules = 0.0, "bajo", []
        key = f"CASE-{index:02d}"
        records.append(
            {
                "contract_key_canon": key,
                "source": source,
                "source_record_id": f"SRC-{index:02d}",
                "source_dataset": "test",
                "source_file": "test.parquet",
                "buyer_name": f"Buyer {index}",
                "buyer_id": f"B-{index}",
                "supplier_name": f"Supplier {index}",
                "supplier_id": f"S-{index}",
                "contract_title": f"Contract {index}",
                "procedure": "Abierto",
                "publication_date": "2024-01-01",
                "award_date": None,
                "estimated_value_eur": 100000.0,
                "awarded_value_eur": 90000.0,
                "cpv_codes_raw": "71000000",
                "cpv_code_list": "71000000",
            }
        )
        score_records.append(
            {
                "contract_key_canon": key,
                "risk_score": score,
                "risk_level": level,
                "flags_count": len(rules),
                "top_flags": json.dumps(rules),
                "score_version": "test",
                "source_snapshot_id": "snapshot-test",
                "agent3_features_used": False,
                "evaluable_rules_count": 5,
                "not_evaluable_rules": json.dumps(["RF-06"]),
                "evaluation_status": "partially_evaluable",
                "source_hint": hint,
            }
        )
        for rule in rules:
            flag_records.append(
                {
                    "contract_key_canon": key,
                    "flag_code": rule,
                    "severity": "medium",
                    "confidence": 1.0,
                    "evidence_fields": json.dumps(["buyer_name", "supplier_name"]),
                    "evidence_text": f"Evidence for {rule} in {key}.",
                    "rule_version": "1.0.0",
                }
            )
        feature_records.append(
            {
                "contract_key_canon": key,
                "buyer_supplier_recurrence": 2,
                "buyer_supplier_contract_share": 0.5,
                "buyer_degree": 3,
                "supplier_degree": 2,
                "supplier_contracts_count": 2,
                "contract_neighbor_count": 4,
                "community_id": 1,
                "community_size": 10,
                "agent3_version": "test",
            }
        )
    return (
        pd.DataFrame(records),
        pd.DataFrame(score_records),
        pd.DataFrame(flag_records),
        pd.DataFrame(feature_records),
    )


def _source_for_hint(hint: str) -> str:
    if hint in {"medium-2", "control-boe"}:
        return "boe"
    if hint in {"medium-3", "control-opentender"}:
        return "opentender"
    return "place"


if __name__ == "__main__":
    unittest.main()
