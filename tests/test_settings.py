from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from procurewatch.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_default_directories_follow_project_layout(self) -> None:
        settings = Settings()

        self.assertEqual(settings.raw_data_dir, Path("data/raw"))
        self.assertEqual(settings.processed_data_dir, Path("data/processed"))
        self.assertEqual(settings.synthetic_data_dir, Path("data/synthetic"))
        self.assertEqual(settings.models_dir, Path("models"))

    def test_data_dir_env_override_updates_data_subdirectories(self) -> None:
        with patch.dict(os.environ, {"PROCUREWATCH_DATA_DIR": "tmp-data"}):
            settings = Settings.from_env()

        self.assertEqual(settings.raw_data_dir, Path("tmp-data/raw"))
        self.assertEqual(settings.processed_data_dir, Path("tmp-data/processed"))
        self.assertEqual(settings.synthetic_data_dir, Path("tmp-data/synthetic"))


if __name__ == "__main__":
    unittest.main()
