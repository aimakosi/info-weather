"""
Unit tests for core.config (ConfigManager).
Runs with both python -m unittest and pytest.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.config import (
    CONFIG_SCHEMA_VERSION,
    ConfigManager,
)


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="info_weather_test_")
        self.config_path = Path(self.test_dir) / "config.json"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_config_initialization(self):
        """Проверка дефолтных значений из коробки (FR-14 «как у меня»)."""
        cfg = ConfigManager(self.config_path)
        self.assertEqual(cfg.get("schema_version"), CONFIG_SCHEMA_VERSION)
        self.assertEqual(cfg.get("cities"), [])
        self.assertEqual(cfg.get("update_interval_minutes"), 60)
        self.assertEqual(cfg.get("data_source"), "consensus")

        # Проверка сетевых настроек
        network = cfg.get("network")
        self.assertEqual(network["timeout_seconds"], 8.0)
        self.assertEqual(network["retries"], 1)
        self.assertTrue(network["prefer_ipv4"])
        self.assertEqual(network["fetch_timeout_seconds"], 30.0)

        behavior = cfg.get("window_behavior")
        self.assertFalse(behavior["lock_position"])
        self.assertFalse(behavior["on_all_desktops"])
        self.assertFalse(behavior["always_on_top"])
        self.assertFalse(behavior["show_in_taskbar"])

        window_position = cfg.get("window_position")
        self.assertTrue(window_position["save_position"])
        self.assertFalse(window_position["saved"])
        self.assertIsNone(window_position["x"])
        self.assertIsNone(window_position["y"])

        # Проверка дефолтов оформления и темы
        skin = cfg.get("skin")
        self.assertEqual(skin["theme_mode"], "auto_solar")
        self.assertEqual(skin["font_family"], "Serif")
        self.assertEqual(skin["wind_arrow_color"], "#ef4444")

        # Проверка раскладки (шапка, завтра, компас, 6 дней)
        layout = cfg.get("layout")
        types = [b["type"] for b in layout if b["enabled"]]
        self.assertIn("header", types)
        self.assertIn("today_summary", types)
        self.assertIn("metrics_compass", types)
        self.assertIn("daily_forecast", types)

        # Проверка форматов строк
        formats = cfg.get("formats")
        self.assertEqual(formats["t_fmt"], "{t_day}\n{t_night}")
        self.assertEqual(formats["weekend"], "Sa, Su")
        self.assertEqual(formats["date_format"], "DD.MM")

    def test_save_and_reload(self):
        """Проверка сохранения и повторной загрузки."""
        cfg = ConfigManager(self.config_path)
        cfg.set("cities", ["Караганда", "Астана"])
        cfg.set("home_city", "Караганда")
        self.assertTrue(cfg.save())
        self.assertTrue(self.config_path.exists())

        cfg2 = ConfigManager(self.config_path)
        self.assertEqual(cfg2.get("cities"), ["Караганда", "Астана"])
        self.assertEqual(cfg2.get("home_city"), "Караганда")
        self.assertIsInstance(cfg2.all(), dict)
        self.assertEqual(cfg2.all()["home_city"], "Караганда")

    def test_corrupted_config_recovery(self):
        """Проверка восстановления и создания бэкапа при поврежденном JSON."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON NOT COMPLETE ...")

        cfg = ConfigManager(self.config_path)
        # Должен сброситься на дефолты и не падать
        self.assertEqual(cfg.get("schema_version"), CONFIG_SCHEMA_VERSION)

        # Проверяем, что создан бэкап .bak
        backups = list(self.config_path.parent.glob("*.bak"))
        self.assertGreaterEqual(len(backups), 1)

    def test_whitelist_validation(self):
        """Проверка фильтрации неизвестных ключей (whitelist)."""
        data = {
            "schema_version": 1,
            "cities": ["Oslo"],
            "malicious_key": "some_value",
            "skin": {
                "theme_mode": "night",
                "unknown_skin_option": 123,
            },
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        cfg = ConfigManager(self.config_path)
        loaded = cfg.to_dict()
        self.assertEqual(loaded["cities"], ["Oslo"])
        self.assertEqual(loaded["skin"]["theme_mode"], "night")
        # Неизвестные ключи отфильтрованы
        self.assertNotIn("malicious_key", loaded)
        self.assertNotIn("unknown_skin_option", loaded["skin"])

    def test_reset_to_defaults(self):
        """Проверка сброса конфигурации к значениям по умолчанию."""
        cfg = ConfigManager(self.config_path)
        cfg.set("app_language", "en")
        cfg.set("update_interval_minutes", 15)
        self.assertEqual(cfg.get("app_language"), "en")
        self.assertEqual(cfg.get("update_interval_minutes"), 15)

        cfg.reset_to_defaults()
        self.assertEqual(cfg.get("app_language"), "ru")
        self.assertEqual(cfg.get("update_interval_minutes"), 60)

        # Проверяем, что изменения сохранены на диск
        reloaded = ConfigManager(self.config_path)
        self.assertEqual(reloaded.get("app_language"), "ru")
        self.assertEqual(reloaded.get("update_interval_minutes"), 60)


if __name__ == "__main__":
    unittest.main()
