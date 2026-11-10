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
    GeomagneticForecast,
    KpForecastPoint,
    classify_kp_index,
    fetch_geomagnetic_activity_sync,
    fetch_geomagnetic_forecast_sync,
    get_geomagnetic_activity,
)
from models.weather import WeatherForecastData  # noqa: E402
from ui.blocks.astronomy_block import AstronomyBlockWidget  # noqa: E402


class TestGeomagnetic(unittest.TestCase):
    def setUp(self):
        """Isolate module globals and disk cache for every test.

        Background fetch threads started by one test must not leak into the
        next one: they mutate _cached_activity/_is_fetching and used to race
        the async-callback test.
        """
        import core.geomagnetic as gm

        self._gm = gm
        self._saved_state = (
            gm._cached_activity,
            gm._cached_forecast,
            gm._is_fetching,
            gm._is_fetching_forecast,
        )
        gm._cached_activity = None
        gm._cached_forecast = None
        gm._is_fetching = False
        gm._is_fetching_forecast = False

        self._tmp_dir = tempfile.TemporaryDirectory(prefix="geomag_test_")
        tmp = Path(self._tmp_dir.name)
        self._cache_patchers = [
            patch("core.geomagnetic.GEOMAGNETIC_CACHE_FILE", tmp / "geomagnetic.json"),
            patch("core.geomagnetic.GEOMAGNETIC_FORECAST_CACHE_FILE", tmp / "geomagnetic_forecast.json"),
        ]
        for p in self._cache_patchers:
            p.start()

    def tearDown(self):
        for p in self._cache_patchers:
            p.stop()
        self._tmp_dir.cleanup()

        gm = self._gm
        (
            gm._cached_activity,
            gm._cached_forecast,
            gm._is_fetching,
            gm._is_fetching_forecast,
        ) = self._saved_state

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

    @patch("core.http.HttpClient.fetch_json")
    def test_fetch_geomagnetic_forecast_sync(self, mock_fetch_json):
        mock_fetch_json.return_value = [
            {"time_tag": "2026-11-10T00:00:00", "kp": 1.67, "observed": "observed"},
            {"time_tag": "2026-11-10T03:00:00", "kp": 3.67, "observed": "estimated"},
            {"time_tag": "2026-11-10T06:00:00", "kp": 5.33, "observed": "predicted"},
            {"time_tag": "2026-11-10T09:00:00", "kp": 2.0, "observed": "predicted"},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_cache_file = Path(tmp_dir) / "geomagnetic_forecast.json"
            with patch("core.geomagnetic.GEOMAGNETIC_FORECAST_CACHE_FILE", test_cache_file):
                fc = fetch_geomagnetic_forecast_sync(timeout=2.0)

                self.assertEqual(len(fc.points), 4)
                # observed bin is not a forecast, the other three are
                self.assertEqual(len(fc.forecast_points), 3)
                self.assertFalse(fc.points[0].is_forecast)
                self.assertTrue(fc.points[1].is_forecast)
                # Peak of the forecast window is the 5.33 bin -> G1
                self.assertAlmostEqual(fc.max_kp(), 5.33)
                self.assertEqual(fc.forecast_points[1].noaa_scale, "G1")
                self.assertEqual(fc.forecast_points[1].status_key, "geomagnetic_minor_storm")
                self.assertTrue(test_cache_file.is_file())

                # Round-trip serialization keeps the series intact
                restored = GeomagneticForecast.from_dict(fc.to_dict())
                self.assertEqual(len(restored.points), 4)
                self.assertEqual(restored.points[2].kp_index, 5.33)

    @patch("core.http.HttpClient.fetch_json")
    def test_geomagnetic_forecast_uses_extra_headers_kwarg(self, mock_fetch_json):
        """Regression: fetch_json takes extra_headers=, not headers= (silent TypeError)."""
        mock_fetch_json.return_value = [
            {"time_tag": "2026-11-10T00:00:00", "kp": 1.0, "observed": "predicted"},
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_cache_file = Path(tmp_dir) / "geomagnetic_forecast.json"
            with patch("core.geomagnetic.GEOMAGNETIC_FORECAST_CACHE_FILE", test_cache_file):
                fetch_geomagnetic_forecast_sync(timeout=2.0)

        _, kwargs = mock_fetch_json.call_args
        self.assertIn("extra_headers", kwargs)
        self.assertNotIn("headers", kwargs)

    def test_kp_forecast_point_classification(self):
        p = KpForecastPoint(time_tag="2026-11-10T06:00:00", kp_index=6.0, observed="predicted")
        self.assertEqual(p.level, 6)
        self.assertEqual(p.status_key, "geomagnetic_moderate_storm")
        self.assertEqual(p.noaa_scale, "G2")
        self.assertTrue(p.is_forecast)

    def test_astronomy_block_geomagnetic_toggle(self):
        # No background fetch threads: this test only exercises the toggle.
        with patch("core.geomagnetic.fetch_geomagnetic_activity_async"):
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
                    for _ in range(100):
                        if received:
                            break
                        time.sleep(0.05)

                    self.assertEqual(len(received), 1)
                    self.assertEqual(received[0].kp_index, 5.0)
                    self.assertEqual(received[0].noaa_scale, "G1")

        gm._cached_activity = old_cached


if __name__ == "__main__":
    unittest.main()
