"""Unit tests for data layer: resources, wmo_conditions, and offline fallback."""

import unittest

from data.fallback import get_offline_climatology_data
from data.resources import get_era5_baseline, get_major_cities
from data.wmo_conditions import (
    get_condition_text,
    get_geo_timezone_offset_seconds,
    get_wind_direction_info,
    met_symbol_to_wmo,
    wttr_code_to_wmo,
)


class TestDataLayer(unittest.TestCase):
    def test_major_cities_resource(self):
        cities = get_major_cities()
        self.assertGreater(len(cities), 100)
        self.assertIn("москва", cities)
        self.assertIn("лондон", cities)
        moscow = cities["москва"]
        self.assertAlmostEqual(moscow["lat"], 55.7520, delta=0.01)

    def test_era5_baseline_resource(self):
        baseline = get_era5_baseline()
        self.assertIn("attribution", baseline)
        self.assertIn("Copernicus", baseline["attribution"])
        self.assertEqual(len(baseline["monthly"]), 12)

    def test_wmo_conditions_mapping(self):
        # 0: Clear / Sunny
        self.assertIn("Ясно", get_condition_text(0, lang="ru", is_day=False))
        self.assertIn("Sunny", get_condition_text(0, lang="en", is_day=True))

        # MET Norway symbol mapping
        code, is_day = met_symbol_to_wmo("clearsky_night")
        self.assertEqual(code, 0)
        self.assertEqual(is_day, 0)

        code_rain, _ = met_symbol_to_wmo("heavyrain")
        self.assertEqual(code_rain, 65)

        # MET Norway sleet mapping
        code_sleet, _ = met_symbol_to_wmo("sleet")
        self.assertEqual(code_sleet, 68)
        self.assertEqual(get_condition_text(68, lang="ru"), "Дождь со снегом")
        self.assertEqual(get_condition_text(68, lang="en"), "Sleet")

        # wttr.in code mapping
        self.assertEqual(wttr_code_to_wmo(113), 0)
        self.assertEqual(wttr_code_to_wmo(302), 63)
        self.assertEqual(wttr_code_to_wmo(None), 0)

        # Wind direction
        cardinal, desc = get_wind_direction_info(180, lang="ru")
        self.assertEqual(cardinal, "Ю")
        self.assertIn("Южный", desc)

        # Timezone offset
        offset = get_geo_timezone_offset_seconds(55.75, 37.61)  # Moscow
        self.assertEqual(offset, 3 * 3600)

    def test_offline_climatology_generation(self):
        fc = get_offline_climatology_data(55.75, 37.61, city_name="Moscow", lang="en")
        self.assertEqual(fc.city_name, "Moscow")
        self.assertTrue(fc.is_offline)
        self.assertEqual(fc.consensus_level, "S0")
        self.assertEqual(fc.sources_count, 0)
        self.assertTrue(fc.current.low_confidence)
        self.assertIn("era5_climatology", fc.current.sources)
        self.assertEqual(len(fc.hourly), 24)
        self.assertEqual(len(fc.daily), 7)


if __name__ == "__main__":
    unittest.main()
