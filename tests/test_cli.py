from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from procurewatch.cli import doctor


class CliTests(unittest.TestCase):
    def test_doctor_reports_scaffold_status(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = doctor()

        self.assertEqual(exit_code, 0)
        self.assertIn("ProcureWatch Analytics", output.getvalue())
        self.assertIn("Python", output.getvalue())


if __name__ == "__main__":
    unittest.main()
