from __future__ import annotations

import unittest

from procurewatch.data_sources.boe import (
    extract_cpv_codes,
    parse_boe_record,
    parse_eur,
    parse_raw_line,
)


class BoeParserTests(unittest.TestCase):
    def test_parse_standard_raw_line(self) -> None:
        raw_line = (
            '"MINISTERIO DE DEFENSA,Dirección General del INTA,500083225200.,03/01/2014,'
            'Contratación,Suministros,LCVRS de calificación y vuelo de SO/PHI.,'
            'Negociado sin publicidad,Comunidad de Madrid,'
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
            'Subsecretaría de Sanidad, Servicios Sociales e Igualdad.,2013/01PA011.,'
            '03/01/2014,Contratación,Servicios,Servicio de vigilancia en Prado, Alcalá, '
            'Bravo Murillo y Núñez de Balboa.,Abierto,Comunidad de Madrid,'
            '79000000 Servicios a empresas: legislación, mercadotecnia, asesoría, selección '
            'de personal, imprenta y seguridad,79710000 (Servicios de seguridad).,'
            '1.514.342,42 euros,993.924,19 euros,Sasegur, S.L., FBS Seguridad, S.A.,'
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


if __name__ == "__main__":
    unittest.main()
