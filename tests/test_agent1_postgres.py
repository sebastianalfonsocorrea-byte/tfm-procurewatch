from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd
from sqlalchemy import create_engine, text

from procurewatch.agent1.analytical_dataset import build_analytical_datasets
from procurewatch.db import AGENT1_CONTRACTS_TABLE, AGENT1_SUPPLIERS_TABLE


class Agent1PostgresTests(unittest.TestCase):
    def test_build_analytical_datasets_can_persist_to_sqlite_for_mvp(self) -> None:
        with TemporaryDirectory() as temp:
            workspace = Path(temp)
            processed = workspace / "processed"
            processed.mkdir()
            canonical_path = processed / "agent2_contracts_canonical.parquet"
            sqlite_path = workspace / "agent1.db"

            pd.DataFrame(
                [
                    {
                        "contract_key_canon": "contract-1",
                        "source_tender_id": "tender-1",
                        "source_record_id": "record-1",
                        "buyer_name": "Organismo Demo",
                        "buyer_id": "DIR3-DEMO",
                        "procedure": "Abierto",
                        "cpv_codes_raw": "71300000 Servicios de ingeniería",
                        "estimated_value_eur": 100.0,
                        "awarded_value_eur": 90.0,
                        "publication_date": "2024-01-01",
                        "award_date": "2024-01-10",
                        "supplier_id": "B00000001",
                        "supplier_name": "Proveedor Demo",
                        "source": "boe",
                    }
                ]
            ).to_parquet(canonical_path, index=False)

            report = build_analytical_datasets(
                canonical_path=canonical_path,
                output_dir=processed,
                postgres_dsn=f"sqlite:///{sqlite_path}",
                write_postgres=True,
            )

            self.assertIsNotNone(report["postgres_write"])
            engine = create_engine(f"sqlite:///{sqlite_path}", future=True)
            with engine.connect() as connection:
                contracts_count = connection.execute(
                    text(f"SELECT COUNT(*) FROM {AGENT1_CONTRACTS_TABLE}")
                ).scalar_one()
                suppliers_count = connection.execute(
                    text(f"SELECT COUNT(*) FROM {AGENT1_SUPPLIERS_TABLE}")
                ).scalar_one()

            self.assertEqual(contracts_count, 1)
            self.assertEqual(suppliers_count, 1)
            self.assertTrue((processed / "contracts_analytical.parquet").exists())
            self.assertTrue((processed / "suppliers_analytical.parquet").exists())


if __name__ == "__main__":
    unittest.main()
