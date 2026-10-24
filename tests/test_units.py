"""Unit tests for core/units.py conversions and formatting."""

import unittest

from core.units import (
    calculate_apparent_temperature,
    calculate_dew_point,
    celsius_to_fahrenheit,
    convert_pressure,
    convert_temp,
    convert_temp_diff,
    convert_wind_speed,
    fahrenheit_to_celsius,
    format_pressure,
    format_temp,
    format_wind_speed,
    get_beaufort_name,
    get_beaufort_number,
    inhg_to_hpa,
    kmh_to_ms,
    mmhg_to_hpa,
    mph_to_ms,
)


class TestUnits(unittest.TestCase):
    def test_temperature_conversions(self):
        self.assertAlmostEqual(celsius_to_fahrenheit(0), 32.0)
        self.assertAlmostEqual(celsius_to_fahrenheit(100), 212.0)
        self.assertAlmostEqual(celsius_to_fahrenheit(-40), -40.0)
        self.assertAlmostEqual(fahrenheit_to_celsius(32), 0.0)
        self.assertAlmostEqual(fahrenheit_to_celsius(212), 100.0)

        # convert_temp
        self.assertEqual(convert_temp(23.6, "celsius"), 24)
        self.assertEqual(convert_temp(23.6, "fahrenheit"), 74)
        self.assertIsNone(convert_temp(None))

        # convert_temp_diff (no 32 shift)
        self.assertEqual(convert_temp_diff(5, "celsius"), 5)
        self.assertEqual(convert_temp_diff(5, "fahrenheit"), 9)

        # format_temp
        self.assertEqual(format_temp(25, "celsius", show_sign=True), "+25°")
        self.assertEqual(format_temp(-5, "celsius", show_sign=True), "-5°")
        self.assertEqual(format_temp(0, "celsius", show_sign=True), "0°")
        self.assertEqual(format_temp(25, "fahrenheit", show_sign=False, show_unit=True), "77°F")
        self.assertEqual(format_temp(None), "--")

    def test_wind_conversions_and_beaufort(self):
        self.assertAlmostEqual(kmh_to_ms(36), 10.0)
        self.assertAlmostEqual(mph_to_ms(10), 4.4704)

        self.assertEqual(convert_wind_speed(10.0, "m_s"), 10.0)
        self.assertEqual(convert_wind_speed(10.0, "km_h"), 36.0)

        # Beaufort numbers
        self.assertEqual(get_beaufort_number(0.1), 0)
        self.assertEqual(get_beaufort_number(2.0), 2)
        self.assertEqual(get_beaufort_number(12.0), 6)
        self.assertEqual(get_beaufort_number(35.0), 12)
        self.assertEqual(get_beaufort_name(0.1, "ru"), "Штиль")
        self.assertEqual(get_beaufort_name(0.1, "en"), "Calm")

        # format_wind_speed
        self.assertEqual(format_wind_speed(5.0, "m_s", lang="ru"), "5 м/с")
        self.assertEqual(format_wind_speed(5.0, "km_h", lang="en"), "18 km/h")

    def test_pressure_conversions(self):
        # 1013.25 hPa is standard sea level pressure (~760 mmHg, ~29.92 inHg)
        self.assertEqual(convert_pressure(1013.25, "mmhg"), 760)
        self.assertEqual(convert_pressure(1013.25, "inhg"), 29.92)
        self.assertEqual(convert_pressure(1013.25, "hpa"), 1013)

        self.assertAlmostEqual(mmhg_to_hpa(760), 1013.25, delta=1.0)
        self.assertAlmostEqual(inhg_to_hpa(29.92), 1013.21, delta=1.0)

        self.assertEqual(format_pressure(1013.25, "mmhg", lang="ru"), "760 мм рт. ст.")
        self.assertEqual(format_pressure(1013.25, "hpa", lang="en"), "1013 hPa")

    def test_derived_meteorology(self):
        # Apparent temperature
        at = calculate_apparent_temperature(25.0, 3.0, 50.0)
        self.assertIsInstance(at, float)
        self.assertTrue(15 < at < 35)

        # Dew point
        dp = calculate_dew_point(20.0, 50.0)
        self.assertIsInstance(dp, float)
        self.assertTrue(5 < dp < 15)

    def test_extreme_temperatures(self):
        self.assertAlmostEqual(celsius_to_fahrenheit(-60), -76.0)
        self.assertAlmostEqual(celsius_to_fahrenheit(60), 140.0)
        self.assertEqual(format_temp(-50.4, "celsius", show_sign=True), "-50°")
        self.assertEqual(format_temp(48.6, "celsius", show_sign=True), "+49°")

    def test_all_beaufort_levels(self):
        # Test boundaries for all 12 Beaufort levels
        sample_speeds = [0.0, 1.0, 2.5, 4.5, 7.0, 9.5, 12.5, 15.5, 19.0, 22.5, 26.5, 30.5, 35.0]
        for level, speed in enumerate(sample_speeds):
            self.assertEqual(get_beaufort_number(speed), level)
            self.assertTrue(len(get_beaufort_name(speed, "ru")) > 0)
            self.assertTrue(len(get_beaufort_name(speed, "en")) > 0)

    def test_apparent_temperature_extremes(self):
        # Cold wind chill: -15C with 15 m/s wind should feel significantly colder than -15C
        chill = calculate_apparent_temperature(-15.0, 15.0, 80.0)
        self.assertTrue(chill < -20.0)

        # Hot humid condition: +35C with 85% humidity should feel hotter than +35C
        heat = calculate_apparent_temperature(35.0, 1.0, 85.0)
        self.assertTrue(heat > 40.0)


if __name__ == "__main__":
    unittest.main()
