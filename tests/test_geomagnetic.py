"""Unit tests for core/geomagnetic.py NOAA Kp-index and space weather module."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from ui.qt_compat import QApplication

app = QApplication.instance() or QApplication(["test_geomagnetic"])

# Qt widgets below need an existing QApplication instance (created above)
from core.geomagnetic import (  # noqa: E402
    GeomagneticActivity,
    classify_kp_index,
    fetch_geomagnetic_activity_sync,
    get_geomagnetic_activity,
)
from models.weather import WeatherForecastData  # noqa: E402
from ui.blocks.astronomy_block import AstronomyBlockWidget  # noqa: E402


class TestGeomagnetic(unittest.TestCase):
    def test_classify_kp_index(self):
        # Quiet
        level, key, color, scale = classify_kp_index(1.0)
        self.assertEqual(level, 1)
        self.assertEqual(key, "geomagnetic_quiet")
        self.assertEqual(scale, "G0")

        # Unsettled
        level, key, color, scale = classify_kp_index(3.0)
        self.assertEqual(level, 3)
        self.assertEqual(key, "geomagnetic_unsettled")
        self.assertEqual(scale, "G0")

        # Active
        level, key, color, scale = classify_kp_index(4.0)
        self.assertEqual(level, 4)
        self.assertEqual(key, "geomagnetic_active")

        # Storm G1
        level, key, color, scale = classify_kp_index(5.0)
        self.assertEqual(level, 5)
        self.assertEqual(key, "geomagnetic_minor_storm")
        self.assertEqual(scale, "G1")

        # Storm G2
        level, key, color, scale = classify_kp_index(6.0)
        self.assertEqual(level, 6)
        self.assertEqual(key, "geomagnetic_moderate_storm")
        self.assertEqual(scale, "G2")

        # Storm G4
        level, key, color, scale = classify_kp_index(8.0)
        self.assertEqual(level, 8)
        self.assertEqual(key, "geomagnetic_severe_storm")
        self.assertEqual(scale, "G4")

        # Extreme Storm G5
        level, key, color, scale = classify_kp_index(9.0)
        self.assertEqual(level, 9)
        self.assertEqual(key, "geomagnetic_extreme_storm")
        self.assertEqual(scale, "G5")

    def test_serialization(self):
        act = GeomagneticActivity(
            kp_index=3.67,
            level=4,
            status_key="geomagnetic_active",
            color="#eab308",
            noaa_scale="G0",
            observed_at="2026-10-20T18:00:00",
            cached_at=123456789.0,
        )
        d = act.to_dict()
        self.assertEqual(d["kp_index"], 3.67)
        self.assertEqual(d["level"], 4)

        restored = GeomagneticActivity.from_dict(d)
        self.assertEqual(restored.kp_index, 3.67)
        self.assertEqual(restored.status_key, "geomagnetic_active")

    @patch("core.http.HttpClient.fetch_json")
    def test_fetch_geomagnetic_sync(self, mock_fetch_json):
        mock_fetch_json.return_value = [
            {"time_tag": "2026-10-20T12:00:00", "Kp": 2.0},
            {"time_tag": "2026-10-20T15:00:00", "Kp": 3.33},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_cache_file = Path(tmp_dir) / "geomagnetic.json"
            with patch("core.geomagnetic.GEOMAGNETIC_CACHE_FILE", test_cache_file):
                act = fetch_geomagnetic_activity_sync(timeout=2.0)
                self.assertEqual(act.kp_index, 3.33)
                self.assertEqual(act.level, 3)
                self.assertEqual(act.status_key, "geomagnetic_unsettled")
                self.assertTrue(test_cache_file.is_file())

    def test_astronomy_block_geomagnetic_toggle(self):
        # 1. Enabled by default
        block = AstronomyBlockWidget(options={"show_moon": True, "show_geomagnetic": True})
        self.assertTrue(hasattr(block, "geomagnetic_item"))
        data = WeatherForecastData(city_name="Москва", lat=55.75, lon=37.61)
        block.update(data)
        self.assertFalse(block.geomagnetic_item["container"].isHidden())
        self.assertNotEqual(block.geomagnetic_item["val_label"].text(), "—")

        # 2. Disabled via options
        block_off = AstronomyBlockWidget(options={"show_moon": True, "show_geomagnetic": False})
        block_off.update(data)
        self.assertTrue(block_off.geomagnetic_item["container"].isHidden())

    def test_get_geomagnetic_activity_async_callback(self):
        import core.geomagnetic as gm
        # Reset cached activity to simulate cold start
        old_cached = gm._cached_activity
        gm._cached_activity = None

        received = []
        mock_client = MagicMock()
        mock_client.fetch_json.return_value = [
            {"time_tag": "2026-10-22T03:00:00", "Kp": 5.0},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_cache_file = Path(tmp_dir) / "geomagnetic.json"
            with patch("core.geomagnetic.GEOMAGNETIC_CACHE_FILE", test_cache_file):
                with patch("core.http.get_default_http_client", return_value=mock_client):
                    # Cold start returns default quiet activity immediately
                    initial = get_geomagnetic_activity(
                        force_sync=False,
                        on_updated=lambda act: received.append(act),
                    )
                    self.assertEqual(initial.kp_index, 2.0)
                    self.assertFalse(initial.is_cached)

                    # Wait for background thread
                    import time
                    for _ in range(20):
                        if received:
                            break
                        time.sleep(0.05)

                    self.assertEqual(len(received), 1)
                    self.assertEqual(received[0].kp_index, 5.0)
                    self.assertEqual(received[0].noaa_scale, "G1")

        gm._cached_activity = old_cached


if __name__ == "__main__":
    unittest.main()
