from __future__ import annotations

import unittest

import pandas as pd

from procurewatch.agent1.boe_units import add_boe_unit_ids


class BoeAnalysisUnitsTests(unittest.TestCase):
    def test_same_file_has_same_file_id_but_different_award_line_ids(self) -> None:
        dataframe = pd.DataFrame(
            [
                {
                    "notice_id": "BOE-1",
                    "contract_id": "BOE-1",
                    "buyer_name": "Ayuntamiento de Ávila",
                    "file_number": "EXP-01/2024.",
                    "supplier_name": "Proveedor A",
                    "awarded_value_eur": 40.0,
                    "object": "Servicio técnico",
                    "cpv_codes_raw": "71300000 Servicios",
                },
                {
                    "notice_id": "BOE-1",
                    "contract_id": "BOE-1",
                    "buyer_name": "AYUNTAMIENTO DE AVILA",
                    "file_number": "EXP 01 2024",
                    "supplier_name": "Proveedor B",
                    "awarded_value_eur": 60.0,
                    "object": "Servicio técnico",
                    "cpv_codes_raw": "71300000 Servicios",
                },
            ]
        )

        result = add_boe_unit_ids(dataframe)

        self.assertEqual(result["id_expediente"].nunique(), 1)
        self.assertEqual(result["id_linea_adjudicacion"].nunique(), 2)

    def test_identifiers_are_stable_when_rows_are_reordered(self) -> None:
        dataframe = pd.DataFrame(
            [
                {
                    "notice_id": "BOE-1",
                    "contract_id": "BOE-1",
                    "buyer_name": "Organismo",
                    "file_number": "EXP-1",
                    "supplier_name": "Proveedor A",
                    "awarded_value_eur": 40.0,
                    "object": "Servicio",
                    "cpv_codes_raw": "71300000",
                },
                {
                    "notice_id": "BOE-2",
                    "contract_id": "BOE-2",
                    "buyer_name": "Organismo",
                    "file_number": "EXP-2",
                    "supplier_name": "Proveedor B",
                    "awarded_value_eur": 60.0,
                    "object": "Servicio",
                    "cpv_codes_raw": "71300000",
                },
            ]
        )

        original = add_boe_unit_ids(dataframe)
        reordered = add_boe_unit_ids(dataframe.iloc[::-1]).sort_index()

        self.assertEqual(
            original["id_expediente"].tolist(),
            reordered["id_expediente"].tolist(),
        )
        self.assertEqual(
            original["id_linea_adjudicacion"].tolist(),
            reordered["id_linea_adjudicacion"].tolist(),
        )


if __name__ == "__main__":
    unittest.main()
