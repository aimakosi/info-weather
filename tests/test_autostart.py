"""Unit tests for autostart desktop entry management (Stage 6, FR-12)."""

import tempfile
import unittest
from pathlib import Path

from core.autostart import disable_autostart, enable_autostart, is_autostart_enabled


class TestAutostart(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.autostart_file = Path(self.temp_dir.name) / "info-weather.desktop"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_enable_and_check_autostart(self):
        self.assertFalse(is_autostart_enabled(self.autostart_file))

        # Enable without delay
        success = enable_autostart(delay_sec=0, filepath=self.autostart_file)
        self.assertTrue(success)
        self.assertTrue(self.autostart_file.is_file())
        self.assertTrue(is_autostart_enabled(self.autostart_file))

        content = self.autostart_file.read_text(encoding="utf-8")
        self.assertIn("Exec=info-weather --autostart", content)
        self.assertIn("StartupNotify=false", content)

    def test_enable_with_delay(self):
        enable_autostart(delay_sec=5, filepath=self.autostart_file)
        content = self.autostart_file.read_text(encoding="utf-8")
        self.assertIn("--delay 5", content)

    def test_disable_autostart(self):
        enable_autostart(filepath=self.autostart_file)
        self.assertTrue(self.autostart_file.is_file())

        disable_autostart(filepath=self.autostart_file)
        self.assertFalse(self.autostart_file.is_file())
        self.assertFalse(is_autostart_enabled(self.autostart_file))


if __name__ == "__main__":
    unittest.main()
