from __future__ import annotations

import unittest

from procurewatch.data_sources.boe import (
    build_boe_award_lines,
    extract_cpv_codes,
    parse_boe_record,
    parse_eur,
    parse_raw_line,
)


class BoeParserTests(unittest.TestCase):
    def test_parse_standard_raw_line(self) -> None:
        raw_line = (
            '"MINISTERIO DE DEFENSA,Dirección General del INTA,500083225200.,03/01/2014,'
            "Contratación,Suministros,LCVRS de calificación y vuelo de SO/PHI.,"
            "Negociado sin publicidad,Comunidad de Madrid,"
            '""38000000 Equipo de laboratorio, óptico y de precisión (excepto gafas)"",'
            '""38000000 (Equipo de laboratorio, óptico y de precisión (excepto gafas))."",'
            '""120.000,00 euros"",""120.000,00 euros"",""Arcopix, S.A."",'
            'https://www.boe.es/diario_boe/txt.php?id=BOE-B-2014-201";;;;;\n'
        )

        record = parse_boe_record(
            parse_raw_line(raw_line),
            source_file="sample.csv",
            source_line=2,
        )

        self.assertEqual(record.contract_id, "BOE-B-2014-201")
        self.assertEqual(record.publication_date, "2014-01-03")
        self.assertEqual(record.procedure, "Negociado sin publicidad")
        self.assertEqual(record.estimated_value_eur, 120000.0)
        self.assertIn("38000000", record.cpv_code_list)

    def test_parse_line_with_commas_in_institution_object_and_supplier(self) -> None:
        raw_line = (
            '"MINISTERIO DE SANIDAD, SERVICIOS SOCIALES E IGUALDAD,'
            "Subsecretaría de Sanidad, Servicios Sociales e Igualdad.,2013/01PA011.,"
            "03/01/2014,Contratación,Servicios,Servicio de vigilancia en Prado, Alcalá, "
            "Bravo Murillo y Núñez de Balboa.,Abierto,Comunidad de Madrid,"
            "79000000 Servicios a empresas: legislación, mercadotecnia, asesoría, selección "
            "de personal, imprenta y seguridad,79710000 (Servicios de seguridad).,"
            "1.514.342,42 euros,993.924,19 euros,Sasegur, S.L., FBS Seguridad, S.A.,"
            'https://www.boe.es/diario_boe/txt.php?id=BOE-B-2014-219";;;;;\n'
        )

        record = parse_boe_record(
            parse_raw_line(raw_line),
            source_file="sample.csv",
            source_line=13,
        )

        self.assertEqual(record.institution, "MINISTERIO DE SANIDAD, SERVICIOS SOCIALES E IGUALDAD")
        self.assertEqual(record.procedure, "Abierto")
        self.assertEqual(record.awarded_value_eur, 993924.19)
        self.assertEqual(record.supplier_name, "Sasegur, S.L., FBS Seguridad, S.A.")
        self.assertTrue(record.repaired_columns)

    def test_parse_eur_and_cpv_helpers(self) -> None:
        self.assertEqual(parse_eur("2.179.000,50 euros"), 2179000.5)
        self.assertIsNone(parse_eur("No disponible"))
        self.assertEqual(
            extract_cpv_codes("71000000 Servicios; 71300000 Servicios de ingeniería"),
            ["71000000", "71300000"],
        )

    def test_build_boe_award_lines_keeps_lots_and_removes_only_exact_duplicates(self) -> None:
        import pandas as pd

        base = {
            "notice_id": "BOE-1",
            "institution": "Ministerio",
            "buyer_name": "Organismo",
            "file_number": "EXP-1",
            "object": "Servicio",
            "record_type": "Contratación",
            "estimated_value_eur": 100.0,
            "cpv_codes_raw": "71300000 Servicios",
            "cpv_code_list": ["71300000"],
        }
        dataframe = pd.DataFrame(
            [
                {**base, "supplier_name": "Proveedor A", "awarded_value_eur": 40.0},
                {**base, "supplier_name": "Proveedor A", "awarded_value_eur": 40.0},
                {**base, "supplier_name": "Proveedor B", "awarded_value_eur": 60.0},
                {
                    **base,
                    "notice_id": "BOE-2",
                    "file_number": "EXP-2",
                    "supplier_name": "Proveedor C",
                    "awarded_value_eur": 45.0,
                    "cpv_codes_raw": "45000000 y 71300000",
                    "cpv_code_list": ["45000000", "71300000"],
                },
                {
                    **base,
                    "notice_id": "BOE-3",
                    "file_number": "EXP-3",
                    "record_type": "Licitación",
                    "supplier_name": "No disponible",
                    "awarded_value_eur": None,
                },
            ]
        )

        result = build_boe_award_lines(dataframe)

        self.assertEqual(len(result), 2)
        self.assertEqual(set(result["supplier_name"]), {"Proveedor A", "Proveedor B"})


if __name__ == "__main__":
    unittest.main()
