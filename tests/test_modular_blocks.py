import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from ui.qt_compat import QApplication
    _app = QApplication.instance() or QApplication(["test_modular_blocks"])
except ImportError:
    pass

from core.config import ConfigManager
from models.weather import (
    CurrentConditions,
    DailyForecast,
    DayDetailedForecast,
    WeatherForecastData,
)
from ui.blocks.additional_info_block import AdditionalInfoBlock
from ui.blocks.astronomy_block import AstronomyBlock
from ui.blocks.daily_block import DailyBlock
from ui.blocks.day_periods_block import DayPeriodsBlock
from ui.blocks.wind_block import WindBlock


def make_sample_weather_data() -> WeatherForecastData:
    """Helper to create rich weather forecast data for tests."""
    current = CurrentConditions(
        temp=1.0,
        feels_like=-2.0,
        humidity=75,
        pressure_mm=748,
        pressure_hpa=997.0,
        wind_speed=3.0,
        wind_direction=315,
        wind_cardinal="NW",
        dew_point=-3.0,
        condition_text="Mainly cloudy",
        weather_code=3,
        is_day=1,
    )
    daily = [
        DailyForecast(day="Thu", weekday_idx=3, min=-1.0, max=2.0, code=3, icon_name="weather-clouds", precip_prob_max=10, date_str="2026-10-15"),
        DailyForecast(day="Fri", weekday_idx=4, min=-2.0, max=3.0, code=71, icon_name="weather-snow", precip_prob_max=60, date_str="2026-10-16"),
        DailyForecast(day="Sat", weekday_idx=5, min=-3.0, max=2.0, code=61, icon_name="weather-rain", precip_prob_max=50, date_str="2026-10-17"),
        DailyForecast(day="Sun", weekday_idx=6, min=-1.0, max=3.0, code=61, icon_name="weather-rain", precip_prob_max=40, date_str="2026-10-18"),
        DailyForecast(day="Mon", weekday_idx=0, min=-2.0, max=5.0, code=3, icon_name="weather-clouds", precip_prob_max=15, date_str="2026-10-19"),
        DailyForecast(day="Tue", weekday_idx=1, min=2.0, max=11.0, code=61, icon_name="weather-rain", precip_prob_max=70, date_str="2026-10-20"),
    ]
    days_det = [
        DayDetailedForecast(
            day_index=0,
            date_str="2026-10-15",
            hourly_temps=[0] * 24,
            hourly_winds=[3.0] * 24,
            hourly_wind_dirs=[315] * 24,
            hourly_codes=[3] * 24,
            hourly_is_days=[0 if h < 6 or h > 18 else 1 for h in range(24)],
        ),
        DayDetailedForecast(
            day_index=1,
            date_str="2026-10-16",
            hourly_temps=[-1, -1, -1, -1, -2, -2, -2, -2, -2, -2, 0, 1, 2, 2, 2, 2, 1, 1, 0, 0, 0, 0, -1, -1],
            hourly_winds=[1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 1.0, 1.0],
            hourly_wind_dirs=[270] * 24,
            hourly_codes=[71] * 24,
            hourly_is_days=[0 if h < 6 or h > 18 else 1 for h in range(24)],
            wind_max=4.0,
            dominant_wind_cardinal="W",
        ),
    ]
    return WeatherForecastData(
        city_name="Abakan",
        country="RU",
        lat=53.72,
        lon=91.44,
        current=current,
        daily=daily,
        days_detailed=days_det,
    )


class TestModularBlocks(unittest.TestCase):
    def setUp(self):
        self.data = make_sample_weather_data()

    def test_wind_block(self):
        wb = WindBlock(options={"angle": -1.0}, scale=1.0)
        self.assertEqual(wb.angle_offset, -1.0)
        wb.update(self.data)
        self.assertEqual(wb.wind_speed, 3.0)
        self.assertEqual(wb.wind_dir, 315.0)
        self.assertEqual(wb.wind_cardinal, "NW")

    def test_additional_info_block(self):
        ab = AdditionalInfoBlock(scale=1.0)
        ab.update(self.data)
        # Should execute safely in headless or GUI environments
        self.assertEqual(ab.scale, 1.0)

    def test_day_periods_block_tomorrow(self):
        dp_tom = DayPeriodsBlock(options={"mode": "tomorrow", "title": "Завтра"}, scale=1.0)
        self.assertEqual(dp_tom.mode, "tomorrow")
        dp_tom.update(self.data)
        # Check extraction logic
        extracted = dp_tom._extract_periods(self.data, 1)
        self.assertIn("night", extracted)
        self.assertIn("morning", extracted)
        self.assertIn("day", extracted)
        self.assertIn("evening", extracted)
        self.assertEqual(extracted["night"]["temp"], -1)
        self.assertEqual(extracted["morning"]["temp"], -2)
        self.assertEqual(extracted["day"]["temp"], 2)
        self.assertEqual(extracted["evening"]["temp"], 0)

    def test_day_periods_block_today(self):
        dp_tod = DayPeriodsBlock(options={"mode": "today", "title": "Сегодня"}, scale=1.0)
        self.assertEqual(dp_tod.mode, "today")
        dp_tod.update(self.data)
        extracted = dp_tod._extract_periods(self.data, 0)
        self.assertIn("night", extracted)
        self.assertIn("day", extracted)

    def test_astronomy_block(self):
        asb = AstronomyBlock(options={"show_moon": True}, scale=1.0)
        asb.update(self.data)
        self.assertEqual(asb.scale, 1.0)

    def test_daily_block_horizontal_mode(self):
        db = DailyBlock(options={"days": 5, "horizontal": True}, scale=1.0)
        self.assertTrue(db.horizontal)
        db.update(self.data)
        if db.widget is not None:
            self.assertEqual(len(db.rows), 5)
            first_col = db.rows[0]
            # Wind is removed per user requirement
            self.assertIsNone(first_col.get("wind_label"))
            self.assertIsNotNone(first_col.get("cond_label"))
            self.assertIsNotNone(first_col.get("max_label"))
            self.assertIsNotNone(first_col.get("min_label"))

    def test_weather_icon_resolution_not_all_sun(self):
        from ui.utils import discover_icon_themes, get_weather_icon_path

        themes = discover_icon_themes()
        self.assertIn("Meteocons_monochrome", themes)
        self.assertIn("WeatherIcons", themes)
        self.assertIn("svg", themes)

        # WeatherIcons theme (yahoo-coded SVGs, SIL OFL 1.1)
        wi_snow = get_weather_icon_path(code=71, is_day=1, theme="WeatherIcons")
        wi_rain = get_weather_icon_path(code=61, is_day=1, theme="WeatherIcons")
        wi_sun = get_weather_icon_path(code=0, is_day=1, theme="WeatherIcons")
        self.assertTrue(wi_snow.endswith("14.svg"))
        self.assertTrue(wi_rain.endswith("11.svg"))
        self.assertTrue(wi_sun.endswith("32.svg"))

        # Test native vector SVG
        svg_snow = get_weather_icon_path(code=71, is_day=1, theme="svg")
        svg_rain = get_weather_icon_path(code=61, is_day=1, theme="svg")
        svg_sun = get_weather_icon_path(code=0, is_day=1, theme="svg")
        self.assertIn("snow.svg", svg_snow)
        self.assertIn("rain.svg", svg_rain)
        self.assertIn("clear-day.svg", svg_sun)

    def test_service_icons_resolve_to_bundled_svg(self):
        from ui.utils import get_weather_icon_path

        sunrise = get_weather_icon_path("sunrise.svg", theme="WeatherIcons")
        sunset = get_weather_icon_path("sunset.svg", theme="WeatherIcons")
        sun = get_weather_icon_path("sun.svg", theme="WeatherIcons")
        self.assertTrue(sunrise.endswith("sunrise.svg"))
        self.assertTrue(sunset.endswith("sunset.svg"))
        self.assertTrue(sun.endswith("sun.svg"))
        self.assertEqual(len({sunrise, sunset, sun}), 3)

    def test_config_view_blocks_lifecycle(self):
        tmp_dir = tempfile.mkdtemp(prefix="test_view_blocks_")
        try:
            cfg_path = Path(tmp_dir) / "config.json"
            cfg = ConfigManager(cfg_path)
            view_b = cfg.get("view_blocks")
            self.assertIsNotNone(view_b)
            self.assertIn("wind", view_b)
            self.assertIn("now", view_b)
            self.assertIn("tomorrow", view_b)
            self.assertIn("today", view_b)
            self.assertIn("additional_info", view_b)
            self.assertIn("astronomy", view_b)
            self.assertIn("daily", view_b)

            # Test updating 2-axis offsets
            view_b["wind"]["offset_x"] = -180
            view_b["wind"]["offset_y"] = 15
            cfg.set("view_blocks", view_b)

            # Reload
            cfg_reloaded = ConfigManager(cfg_path)
            re_b = cfg_reloaded.get("view_blocks")
            self.assertEqual(re_b["wind"]["offset_x"], -180)
            self.assertEqual(re_b["wind"]["offset_y"], 15)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
