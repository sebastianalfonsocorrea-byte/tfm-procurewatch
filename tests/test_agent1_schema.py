from __future__ import annotations

import unittest

from procurewatch.agent1 import (
    ANALYTICAL_SCHEMA,
    CONTRACT_REQUIRED_FIELDS,
    CONTRACT_SCHEMA,
    SUPPLIER_REQUIRED_FIELDS,
    SUPPLIER_SCHEMA,
)


class Agent1AnalyticalSchemaTests(unittest.TestCase):
    def test_contract_schema_contains_all_proposal_fields(self) -> None:
        self.assertEqual(set(CONTRACT_SCHEMA), set(CONTRACT_REQUIRED_FIELDS))

    def test_supplier_schema_contains_all_proposal_fields(self) -> None:
        self.assertEqual(set(SUPPLIER_SCHEMA), set(SUPPLIER_REQUIRED_FIELDS))

    def test_every_field_declares_type_owner_nullability_and_allowed_values(self) -> None:
        for entity_schema in (CONTRACT_SCHEMA, SUPPLIER_SCHEMA):
            for field_name, definition in entity_schema.items():
                with self.subTest(field=field_name):
                    self.assertIn("type", definition)
                    self.assertIn("owner", definition)
                    self.assertIn("nullable", definition)
                    self.assertIn("allowed_values", definition)
                    self.assertIn("description", definition)

    def test_proposal_enumerations_are_preserved(self) -> None:
        self.assertEqual(
            CONTRACT_SCHEMA["nivel_administracion"]["allowed_values"],
            ["central", "autonomica", "local"],
        )
        self.assertEqual(
            CONTRACT_SCHEMA["nivel_riesgo"]["allowed_values"],
            ["bajo", "medio", "alto", "critico"],
        )
        self.assertEqual(
            CONTRACT_SCHEMA["estado_revision"]["allowed_values"],
            ["pendiente", "en_revision", "cerrado"],
        )

    def test_schema_identifies_proposal_as_source(self) -> None:
        self.assertIn("apartado 5.4", ANALYTICAL_SCHEMA["source"])


if __name__ == "__main__":
    unittest.main()
