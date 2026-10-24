"""Golden tests for Open-Meteo, MET Norway, and wttr.in clients on offline fixtures."""

import json
import unittest
from pathlib import Path

from providers.clients.met_norway import MetNorwayClient
from providers.clients.open_meteo import OpenMeteoClient
from providers.clients.wttr import WttrClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "api"


class TestClientsNormalization(unittest.TestCase):
    def test_open_meteo_normal_fixture(self):
        fixture_path = FIXTURES_DIR / "open_meteo" / "best_match_normal.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        client = OpenMeteoClient()
        fc = client.normalize_response(raw, lat=49.80, lon=73.10, fetched_at=1000.0)

        self.assertEqual(fc.source_name, "open_meteo")
        self.assertFalse(fc.is_basic_mode)
        self.assertEqual(fc.depth_days, 7)

        # Check current observation
        self.assertAlmostEqual(fc.current.temp, 11.2)
        self.assertEqual(fc.current.weather_code, 3)
        self.assertEqual(fc.current.is_day, 1)
        self.assertAlmostEqual(fc.current.wind_speed, 4.2)
        self.assertAlmostEqual(fc.current.pressure_msl, 1018.4)
        self.assertAlmostEqual(fc.current.humidity, 62.0)

        # Check hourly
        self.assertGreaterEqual(len(fc.hourly), 24)
        h0 = fc.hourly[0]
        self.assertTrue(h0.time_iso.endswith("Z"))
        self.assertAlmostEqual(h0.temp, 6.5)

        # Check daily
        self.assertEqual(len(fc.daily), 7)
        d0 = fc.daily[0]
        self.assertEqual(d0.date_str, "2026-10-14")
        self.assertAlmostEqual(d0.temp_min, 4.0)
        self.assertAlmostEqual(d0.temp_max, 14.0)

    def test_open_meteo_minimal_fixture(self):
        fixture_path = FIXTURES_DIR / "open_meteo" / "best_match_minimal.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        client = OpenMeteoClient()
        fc = client.normalize_response(raw, lat=49.80, lon=73.10)
        self.assertAlmostEqual(fc.current.temp, 11.2)
        self.assertEqual(len(fc.hourly), 0)
        self.assertEqual(len(fc.daily), 3)

    def test_met_norway_normal_fixture(self):
        fixture_path = FIXTURES_DIR / "met_norway" / "normal.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        client = MetNorwayClient()
        fc = client.normalize_response(raw, lat=49.80, lon=73.10, fetched_at=2000.0)

        self.assertEqual(fc.source_name, "met_norway")
        self.assertFalse(fc.is_basic_mode)

        # Current
        self.assertAlmostEqual(fc.current.temp, 14.8)
        self.assertAlmostEqual(fc.current.pressure_msl, 1029.2)
        self.assertAlmostEqual(fc.current.humidity, 49.1)
        self.assertAlmostEqual(fc.current.wind_speed, 3.7)
        self.assertIsNone(fc.current.visibility)  # MET Norway does not provide visibility

        # Hourly
        self.assertGreater(len(fc.hourly), 24)
        self.assertTrue(fc.hourly[0].time_iso.endswith("Z"))

        # Daily
        self.assertGreaterEqual(len(fc.daily), 5)
        d0 = fc.daily[0]
        self.assertEqual(d0.date_str, "2026-10-14")
        self.assertTrue(d0.temp_min <= d0.temp_max)

    def test_met_norway_karaganda_fixture(self):
        fixture_path = FIXTURES_DIR / "met_norway" / "karaganda_normal.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        client = MetNorwayClient()
        fc = client.normalize_response(raw, lat=49.80, lon=73.10)
        self.assertIsNotNone(fc.current)
        self.assertGreater(len(fc.hourly), 10)

    def test_wttr_normal_fixture(self):
        fixture_path = FIXTURES_DIR / "wttr" / "normal.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        client = WttrClient()
        fc = client.normalize_response(raw, lat=49.80, lon=73.10, fetched_at=3000.0)

        self.assertEqual(fc.source_name, "wttr")
        self.assertTrue(fc.is_basic_mode)
        self.assertLessEqual(fc.depth_days, 3)

        # Current (temp_C: 13, wind: 18 km/h -> 5.0 m/s)
        self.assertAlmostEqual(fc.current.temp, 13.0)
        self.assertAlmostEqual(fc.current.wind_speed, 5.0)
        self.assertEqual(fc.current.weather_code, 3)
        self.assertAlmostEqual(fc.current.pressure_msl, 1030.0)
        self.assertAlmostEqual(fc.current.visibility, 10.0)

        # Daily (3 days)
        self.assertEqual(len(fc.daily), 3)
        d0 = fc.daily[0]
        self.assertEqual(d0.date_str, "2026-10-14")
        self.assertAlmostEqual(d0.temp_min, 5.0)
        self.assertAlmostEqual(d0.temp_max, 15.0)

    def test_wttr_local_times_converted_to_utc(self):
        """wttr.in local clock times must be shifted to UTC, not labeled as UTC."""
        raw = {
            "current_condition": [{"temp_C": "10", "windspeedKmph": "10",
                                   "winddirDegree": "90", "weatherCode": "113"}],
            "weather": [{
                "date": "2026-10-14",
                "mintempC": "5.0",
                "maxtempC": "15.0",
                "hourly": [
                    {"time": "0", "tempC": "5.0", "weatherCode": "113",
                     "windspeedKmph": "10", "winddirDegree": "90",
                     "chanceofrain": "10", "chanceofsnow": "0"},
                    {"time": "1500", "tempC": "12.0", "weatherCode": "113",
                     "windspeedKmph": "10", "winddirDegree": "90",
                     "chanceofrain": "10", "chanceofsnow": "0"},
                ],
            }],
        }

        client = WttrClient()
        # lon 73.1 -> UTC+6 by the offline estimate: 00:00 local = 18:00Z previous day
        fc = client.normalize_response(raw, lat=49.80, lon=73.10, fetched_at=3000.0)
        self.assertEqual(fc.hourly[0].time_iso, "2026-10-13T18:00:00Z")
        self.assertEqual(fc.hourly[1].time_iso, "2026-10-14T09:00:00Z")
        # Daily stays on the local calendar day reported by wttr
        self.assertEqual(fc.daily[0].date_str, "2026-10-14")

    def test_wttr_missing_optional_fields_are_none(self):
        """Missing humidity/pressure/visibility keys must not fabricate values."""
        raw = {
            "current_condition": [{"temp_C": "10", "windspeedKmph": "10",
                                   "winddirDegree": "90", "weatherCode": "113"}],
            "weather": [{
                "date": "2026-10-14", "mintempC": "5.0", "maxtempC": "15.0",
                "hourly": [{"time": "900", "tempC": "8.0", "weatherCode": "113",
                            "windspeedKmph": "10", "winddirDegree": "90",
                            "chanceofrain": "0", "chanceofsnow": "0"}],
            }],
        }

        client = WttrClient()
        fc = client.normalize_response(raw, lat=49.80, lon=73.10, fetched_at=3000.0)
        self.assertIsNone(fc.current.humidity)
        self.assertIsNone(fc.current.pressure_msl)
        self.assertIsNone(fc.current.visibility)
        self.assertIsNone(fc.hourly[0].humidity)


if __name__ == "__main__":
    unittest.main()
