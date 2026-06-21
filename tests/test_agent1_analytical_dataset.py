from __future__ import annotations

import unittest

import pandas as pd

from procurewatch.agent1 import (
    CONTRACT_REQUIRED_FIELDS,
    SUPPLIER_REQUIRED_FIELDS,
    build_supplier_analytical_table,
    map_contracts_to_analytical_schema,
)


class Agent1AnalyticalDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canonical = pd.DataFrame(
            [
                {
                    "contract_key_canon": "contract-1",
                    "source": "place",
                    "source_record_id": "licitacion-1",
                    "buyer_name": "Ayuntamiento Norte",
                    "buyer_id": "L010000",
                    "supplier_name": "Proveedor Á",
                    "supplier_id": "B99286320",
                    "procedure": "Abierto",
                    "publication_date": "2024-01-01",
                    "award_date": "2024-01-11",
                    "estimated_value_eur": 100.0,
                    "awarded_value_eur": 90.0,
                    "cpv_codes_raw": "71300000 Servicios de ingeniería",
                },
                {
                    "contract_key_canon": "contract-2",
                    "source": "opentender",
                    "source_record_id": "licitacion-2",
                    "buyer_name": "Ayuntamiento Sur",
                    "buyer_id": "",
                    "supplier_name": "Proveedor A",
                    "supplier_id": "B99286320",
                    "procedure": "Negociado sin publicidad",
                    "publication_date": "2024-02-10",
                    "award_date": "",
                    "estimated_value_eur": 0.0,
                    "awarded_value_eur": 50.0,
                    "cpv_codes_raw": "71300000",
                },
                {
                    "contract_key_canon": "contract-3",
                    "source": "boe",
                    "source_record_id": "boe-3",
                    "buyer_name": "Ministerio",
                    "buyer_id": "ADMINISTRACION GENERAL DEL ESTADO",
                    "supplier_name": "Proveedor B",
                    "supplier_id": "",
                    "procedure": "Abierto",
                    "publication_date": "2024-03-01",
                    "award_date": "",
                    "estimated_value_eur": 200.0,
                    "awarded_value_eur": 180.0,
                    "cpv_codes_raw": "71300000 Servicios de ingeniería",
                },
            ]
        )

    def test_contract_mapping_uses_required_schema_and_derives_only_available_values(self) -> None:
        contracts = map_contracts_to_analytical_schema(self.canonical)

        self.assertEqual(list(contracts.columns), list(CONTRACT_REQUIRED_FIELDS))
        self.assertEqual(contracts.loc[0, "cpv_codigo"], "71300000")
        self.assertEqual(contracts.loc[0, "cpv_descripcion"], "Servicios de ingeniería")
        self.assertEqual(contracts.loc[0, "procedimiento"], "abierto")
        self.assertEqual(contracts.loc[0, "ratio_desviacion_importe"], -0.1)
        self.assertEqual(contracts.loc[0, "dias_resolucion"], 10)
        self.assertEqual(contracts.loc[0, "fuentes_cruzadas"], ["place"])
        self.assertEqual(contracts.loc[0, "estado_revision"], "pendiente")

        self.assertTrue(pd.isna(contracts.loc[1, "ratio_desviacion_importe"]))
        self.assertTrue(pd.isna(contracts.loc[1, "dias_resolucion"]))
        self.assertTrue(pd.isna(contracts.loc[1, "numero_ofertas_recibidas"]))
        self.assertTrue(pd.isna(contracts.loc[1, "score_red_flags_total"]))
        self.assertTrue(pd.isna(contracts.loc[1, "score_centralidad_red"]))
        self.assertTrue(pd.isna(contracts.loc[2, "codigo_organismo"]))

    def test_supplier_table_aggregates_contracts_without_inventing_enrichment(self) -> None:
        contracts = map_contracts_to_analytical_schema(self.canonical)
        suppliers = build_supplier_analytical_table(contracts)

        self.assertEqual(list(suppliers.columns), list(SUPPLIER_REQUIRED_FIELDS))
        supplier_with_nif = suppliers[suppliers["nif"] == "B99286320"].iloc[0]
        self.assertEqual(len(suppliers), 2)
        self.assertEqual(supplier_with_nif["total_contratos"], 2)
        self.assertEqual(supplier_with_nif["total_importe_adjudicado"], 140.0)
        self.assertEqual(supplier_with_nif["organismos_distintos"], 2)
        self.assertTrue(pd.isna(supplier_with_nif["forma_juridica"]))
        self.assertTrue(pd.isna(supplier_with_nif["score_riesgo_agregado"]))


if __name__ == "__main__":
    unittest.main()
