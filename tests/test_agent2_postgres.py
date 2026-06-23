from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from sqlalchemy import create_engine, text

from procurewatch.agent2 import run_agent2
from procurewatch.db import AGENT2_OUTPUTS_TABLE
from procurewatch.db import AGENT2_RISK_FLAGS_TABLE
from procurewatch.db import AGENT2_RISK_SCORES_TABLE


class Agent2PostgresTests(unittest.TestCase):
    def test_run_agent2_can_persist_minimal_tables_for_mvp(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "canonical.parquet"
            sqlite_path = root / "agent2.db"

            pd.DataFrame(
                [
                    {
                        "contract_key_canon": "contract-1",
                        "buyer_name": "Organismo Demo",
                        "supplier_name": "Proveedor Demo",
                        "source_tender_id": "tender-1",
                        "procedure": "Menor",
                        "publication_date": "2024-01-01",
                        "award_date": "2024-01-03",
                        "estimated_value_eur": 100.0,
                        "awarded_value_eur": 120.0,
                    }
                ]
            ).to_parquet(input_path, index=False)

            report = run_agent2(
                input_path=input_path,
                output_dir=root / "processed",
                postgres_dsn=f"sqlite:///{sqlite_path}",
                write_postgres=True,
            )

            self.assertIsNotNone(report["postgres_write"])
            self.assertTrue((root / "processed" / "agent2_risk_flags.parquet").exists())
            self.assertTrue((root / "processed" / "agent2_risk_scores.parquet").exists())

            engine = create_engine(f"sqlite:///{sqlite_path}", future=True)
            try:
                with engine.connect() as connection:
                    flags_count = connection.execute(
                        text(f"SELECT COUNT(*) FROM {AGENT2_RISK_FLAGS_TABLE}")
                    ).scalar_one()
                    scores_count = connection.execute(
                        text(f"SELECT COUNT(*) FROM {AGENT2_RISK_SCORES_TABLE}")
                    ).scalar_one()
                    outputs_count = connection.execute(
                        text(f"SELECT COUNT(*) FROM {AGENT2_OUTPUTS_TABLE}")
                    ).scalar_one()
                    payload = connection.execute(
                        text(
                            f"SELECT payload_json FROM {AGENT2_OUTPUTS_TABLE} "
                            "ORDER BY artifact_type LIMIT 1"
                        )
                    ).scalar_one()
            finally:
                engine.dispose()

            self.assertEqual(flags_count, report["activated_flags"])
            self.assertEqual(scores_count, report["rows"])
            self.assertEqual(outputs_count, 3)
            self.assertEqual(json.loads(payload)["report_path"], report["report_path"])


if __name__ == "__main__":
    unittest.main()
