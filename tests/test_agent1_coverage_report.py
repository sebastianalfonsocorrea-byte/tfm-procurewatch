from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from procurewatch.agent1 import CONTRACT_REQUIRED_FIELDS, build_agent1_coverage_report


class Agent1CoverageReportTests(unittest.TestCase):
    def test_report_separates_schema_presence_from_real_data_coverage(self) -> None:
        import pandas as pd

        row = {field: None for field in CONTRACT_REQUIRED_FIELDS}
        row.update(
            {
                "id_contrato": "contract-1",
                "id_licitacion": "tender-1",
                "organismo_contratante": "Organismo",
                "procedimiento": "abierto",
                "cpv_codigo": "71300000",
                "importe_adjudicado": 100.0,
                "fecha_publicacion": "2024-01-01",
                "nombre_adjudicatario": "Proveedor",
                "fuentes_cruzadas": ["boe"],
                "estado_revision": "pendiente",
            }
        )

        with TemporaryDirectory() as temp:
            root = Path(temp)
            contracts_path = root / "contracts.parquet"
            pd.DataFrame([row]).to_parquet(contracts_path, index=False)

            report = build_agent1_coverage_report(
                contracts_path=contracts_path,
                output_dir=root,
            )

            self.assertEqual(report["schema"]["status"], "complete")
            self.assertEqual(report["overall_status"], "partial")
            self.assertEqual(
                report["quality_metrics"]["ocds_critical_completeness"]["status"],
                "met",
            )
            self.assertEqual(
                report["quality_metrics"]["supplier_nif_coverage"]["status"],
                "not_met",
            )
            self.assertEqual(
                report["quality_metrics"]["temporal_coherence"]["status"],
                "not_evaluable",
            )
            self.assertEqual(report["scope"]["sources_present"], ["boe"])
            self.assertTrue((root / "agent1_coverage_report.json").exists())
            self.assertTrue((root / "agent1_coverage_report.md").exists())


if __name__ == "__main__":
    unittest.main()
