"""Unit tests for core/astronomy.py NOAA solar and lunar calculations."""

import unittest
from datetime import date, datetime, timezone

from core.astronomy import (
    calculate_annual_solar_table,
    calculate_detailed_moon,
    calculate_lunar_distance_km,
    calculate_moon_phase,
    calculate_solar_details,
    compute_solar_uv,
    determine_solar_time_of_day,
)


class TestAstronomy(unittest.TestCase):
    def test_solar_details(self):
        # Karaganda (lat: 49.8028, lon: 73.1025, UTC+5) on equinox
        dt = date(2026, 3, 21)
        res = calculate_solar_details(lat=49.8028, lon=73.1025, dt=dt, utc_offset_hours=5.0)

        self.assertIn("sunrise", res)
        self.assertIn("sunset", res)
        self.assertIn("daylight_duration", res)
        self.assertRegex(res["daylight_duration"], r"^\d{2}:\d{2}$")
        self.assertIn("curve_points", res)
        self.assertEqual(len(res["curve_points"]), 97)

        # On equinox, daylight should be roughly 12 hours (720 min +- 30 min)
        self.assertTrue(660 <= res["daylight_min"] <= 780, f"Daylight {res['daylight_min']} out of range")

    def test_determine_solar_time_of_day(self):
        # Local noon in London (lat: 51.5, lon: 0.0) at 12:00 UTC on summer solstice
        noon_utc = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        tod, is_day = determine_solar_time_of_day(lat=51.5, lon=0.0, utc_dt=noon_utc)
        self.assertEqual(tod, "day")
        self.assertEqual(is_day, 1)

        # Midnight in London
        midnight_utc = datetime(2026, 6, 21, 0, 0, tzinfo=timezone.utc)
        tod_night, is_day_night = determine_solar_time_of_day(lat=51.5, lon=0.0, utc_dt=midnight_utc)
        self.assertEqual(tod_night, "night")
        self.assertEqual(is_day_night, 0)

    def test_moon_calculations(self):
        dt = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
        phase = calculate_moon_phase(dt)
        self.assertIn("cycle_fraction", phase)
        self.assertTrue(0.0 <= phase["cycle_fraction"] <= 1.0)
        self.assertTrue(0 <= phase["illumination"] <= 100)
        self.assertIn("phase_name", phase)

        # Distance to Moon in km (typically 356,000 to 406,000 km)
        dist = calculate_lunar_distance_km(dt)
        self.assertTrue(350000 <= dist <= 410000, f"Distance {dist} out of range")

        # Detailed moon
        detailed = calculate_detailed_moon(lat=55.75, lon=37.61, target_dt=dt, utc_offset_hours=3.0)
        self.assertIn("distance_str", detailed)
        self.assertIn("moonrise", detailed)
        self.assertIn("moonset", detailed)

    def test_solar_uv(self):
        # Summer noon under clear sky: UV should be noticeable (5 - 10)
        noon_dt = datetime(2026, 6, 21, 12, 0)
        uv_clear = compute_solar_uv(lat=45.0, dt=noon_dt, cloud_pct=0.0)
        self.assertTrue(4.0 <= uv_clear <= 12.0, f"UV {uv_clear} out of range")

        # Overcast sky should attenuate UV
        uv_cloudy = compute_solar_uv(lat=45.0, dt=noon_dt, cloud_pct=100.0)
        self.assertTrue(uv_cloudy < uv_clear)

        # Midnight: UV must be 0
        midnight_dt = datetime(2026, 6, 21, 0, 0)
        uv_night = compute_solar_uv(lat=45.0, dt=midnight_dt, cloud_pct=0.0)
        self.assertEqual(uv_night, 0.0)

    def test_annual_solar_table(self):
        res = calculate_annual_solar_table(lat=55.75, lon=37.61, utc_offset_hours=3.0)
        self.assertEqual(len(res["months"]), 12)
        # June daylight > December daylight in Northern hemisphere
        june_dl = res["months"][5]["daylight_min"]
        dec_dl = res["months"][11]["daylight_min"]
        self.assertTrue(june_dl > dec_dl)

    def test_polar_sun_extremes(self):
        # Longyearbyen Svalbard (lat: 78.22, lon: 15.65)
        # Summer solstice: midnight sun
        summer_dt = date(2026, 6, 21)
        res_summer = calculate_solar_details(lat=78.22, lon=15.65, dt=summer_dt, utc_offset_hours=2.0)
        self.assertEqual(res_summer["daylight_min"], 1440)

        # Winter solstice: polar night
        winter_dt = date(2026, 12, 21)
        res_winter = calculate_solar_details(lat=78.22, lon=15.65, dt=winter_dt, utc_offset_hours=1.0)
        self.assertEqual(res_winter["daylight_min"], 0)

    def test_twilight_ordering(self):
        # On normal latitude, dawn <= sunrise <= sunset <= dusk
        dt = date(2026, 4, 15)
        res = calculate_solar_details(lat=55.75, lon=37.61, dt=dt, utc_offset_hours=3.0)
        self.assertTrue(res["t_dawn_frac"] <= res["t_sunrise_frac"])
        self.assertTrue(res["t_sunrise_frac"] <= res["t_sunset_frac"])
        self.assertTrue(res["t_sunset_frac"] <= res["t_dusk_frac"])


if __name__ == "__main__":
    unittest.main()

