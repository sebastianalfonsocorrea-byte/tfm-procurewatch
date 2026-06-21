from __future__ import annotations

import unittest

import pandas as pd

from procurewatch.agent1.buyer_catalog import (
    build_buyer_catalog_index,
    enrich_contracts_with_buyer_catalog_frame,
)


class BuyerCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = pd.DataFrame(
            [
                {
                    "ID Plataforma": "1001",
                    "Nombre Órgano Contratación": "Ayuntamiento de Ávila",
                    "Ubicación sector público": "ENTIDADES LOCALES",
                    "NIF": "P0501900E",
                    "DIR3": "L01010012",
                },
                {
                    "ID Plataforma": "1002",
                    "Nombre Órgano Contratación": "Consejería de Hacienda",
                    "Ubicación sector público": "COMUNIDADES Y CIUDADES AUTÓNOMAS",
                    "NIF": "S0123456A",
                    "DIR3": "D01000001",
                },
                {
                    "ID Plataforma": "2001",
                    "Nombre Órgano Contratación": "Entidad Ambigua",
                    "Ubicación sector público": "ENTIDADES LOCALES",
                    "NIF": "A11111111",
                    "DIR3": "D11111111",
                },
                {
                    "ID Plataforma": "2002",
                    "Nombre Órgano Contratación": "Entidad Ambigua",
                    "Ubicación sector público": "ENTIDADES LOCALES",
                    "NIF": "B22222222",
                    "DIR3": "D22222222",
                },
                {
                    "ID Plataforma": "3001",
                    "Nombre Órgano Contratación": "Entidad Otras",
                    "Ubicación sector público": "OTRAS ENTIDADES DEL SECTOR PÚBLICO",
                    "NIF": "C33333333",
                    "DIR3": "D33333333",
                },
            ]
        )
        self.contracts = pd.DataFrame(
            [
                {
                    "organismo_contratante": "Ayuntamiento de Avila",
                    "codigo_organismo": "",
                    "nivel_administracion": "",
                },
                {
                    "organismo_contratante": "Consejeria de Hacienda",
                    "codigo_organismo": "keep-this",
                    "nivel_administracion": "central",
                },
                {
                    "organismo_contratante": "Entidad Ambigua",
                    "codigo_organismo": "",
                    "nivel_administracion": "",
                },
                {
                    "organismo_contratante": "Entidad Otras",
                    "codigo_organismo": "",
                    "nivel_administracion": "",
                },
            ]
        )

    def test_index_uses_safe_unique_matches(self) -> None:
        index = build_buyer_catalog_index(self.catalog)

        self.assertEqual(index.loc[index["_buyer_catalog_key"] == "AYUNTAMIENTO DE AVILA", "codigo_organismo_catalog"].iloc[0], "L01010012")
        self.assertEqual(index.loc[index["_buyer_catalog_key"] == "AYUNTAMIENTO DE AVILA", "nivel_administracion_catalog"].iloc[0], "local")
        self.assertEqual(index.loc[index["_buyer_catalog_key"] == "ENTIDAD AMBIGUA", "catalog_match_method"].iloc[0], "ambiguous")
        self.assertTrue(pd.isna(index.loc[index["_buyer_catalog_key"] == "ENTIDAD OTRAS", "nivel_administracion_catalog"].iloc[0]))

    def test_enrichment_fills_only_missing_fields(self) -> None:
        enriched, report = enrich_contracts_with_buyer_catalog_frame(self.contracts, self.catalog)

        self.assertEqual(enriched.loc[0, "codigo_organismo"], "L01010012")
        self.assertEqual(enriched.loc[0, "nivel_administracion"], "local")
        self.assertEqual(enriched.loc[1, "codigo_organismo"], "keep-this")
        self.assertEqual(enriched.loc[1, "nivel_administracion"], "central")
        self.assertTrue(pd.isna(enriched.loc[2, "codigo_organismo"]))
        self.assertEqual(enriched.loc[2, "nivel_administracion"], "local")
        self.assertTrue(pd.isna(enriched.loc[3, "nivel_administracion"]))
        self.assertEqual(report["filled_codigo_organismo"], 2)
        self.assertEqual(report["filled_nivel_administracion"], 2)
        self.assertEqual(report["rows_with_any_fill"], 3)
        self.assertEqual(report["unmatched_rows"], 0)


if __name__ == "__main__":
    unittest.main()
