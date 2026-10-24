"""Unit tests for core/cache.py atomic caching and replay functionality."""

import tempfile
import unittest
from pathlib import Path

from core.cache import CacheManager


class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)
        self.cache = CacheManager(cache_dir=self.cache_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_forecast_caching(self):
        lat, lon = 55.75, 37.61
        self.assertIsNone(self.cache.get_forecast(lat, lon))

        data = {"city_name": "Moscow", "temp": 15, "forecast_source": "consensus"}
        self.cache.set_forecast(lat, lon, data)

        cached = self.cache.get_forecast(lat, lon)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["city_name"], "Moscow")
        self.assertEqual(cached["temp"], 15)

        # Invalidate
        self.cache.invalidate_forecast(lat, lon)
        self.assertIsNone(self.cache.get_forecast(lat, lon))

    def test_source_responses_and_replay(self):
        lat, lon = 49.80, 73.10
        om_raw = {"temperature_2m": [10.5, 12.0]}
        met_raw = {"air_temperature": 11.2}

        self.cache.save_source_response("open_meteo", lat, lon, om_raw, fetched_at=1000.0)
        self.cache.save_source_response("met_norway", lat, lon, met_raw, fetched_at=1005.0)

        # Test single retrieval
        om_entry = self.cache.get_source_response("open_meteo", lat, lon)
        self.assertIsNotNone(om_entry)
        self.assertEqual(om_entry["fetched_at"], 1000.0)
        self.assertEqual(om_entry["data"]["temperature_2m"], [10.5, 12.0])

        # Test replay sources
        replay = self.cache.get_replay_sources(lat, lon)
        self.assertEqual(len(replay), 2)
        self.assertIn("open_meteo", replay)
        self.assertIn("met_norway", replay)
        self.assertEqual(replay["met_norway"]["data"]["air_temperature"], 11.2)

    def test_geocache(self):
        query = "London"
        self.assertIsNone(self.cache.get_geocache(query))

        res = [{"name": "London", "lat": 51.5, "lon": -0.12}]
        self.cache.set_geocache(query, res)

        cached = self.cache.get_geocache("london")  # Case insensitive
        self.assertIsNotNone(cached)
        self.assertEqual(cached[0]["name"], "London")

    def test_persistence_across_instances(self):
        lat, lon = 43.22, 76.85
        self.cache.set_forecast(lat, lon, {"city": "Almaty", "temp": 20})

        # New instance pointing to same file
        new_cache = CacheManager(cache_dir=self.cache_dir)
        val = new_cache.get_forecast(lat, lon)
        self.assertIsNotNone(val)
        self.assertEqual(val["city"], "Almaty")


if __name__ == "__main__":
    unittest.main()
