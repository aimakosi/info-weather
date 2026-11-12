"""Tests verifying review fixes:
1. Open-Meteo wind_speed_unit in build_forecast_url.
2. Climate norms bounded adjustments & Southern Hemisphere handling.
3. ClimateNormsWidget supports Celsius and Fahrenheit with proper conversion.
4. Glanceable rail Tab 0 and summary bar convert temperatures according to temp_unit.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from core.config import ConfigManager
from core.i18n import t
from data.fallback import get_adjusted_era5_monthly_norms
from models.weather import CurrentConditions, WeatherForecastData
from providers.clients.open_meteo import OpenMeteoClient
from ui.qt_compat import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(["test_fixes_review"])

from ui.dialogs.detailed_forecast_dialog import (  # noqa: E402
    ClimateNormsWidget,
    DetailedForecastDialogQt,
)


class TestReviewFixes(unittest.TestCase):
    def test_open_meteo_url_wind_speed_unit(self):
        client = OpenMeteoClient()
        url = client.build_forecast_url(55.75, 37.62)
        self.assertIn("wind_speed_unit=ms", url)

    def test_climate_norms_bounded_and_southern_hemisphere(self):
        # 1. Northern temperate (Moscow)
        moscow_norms = get_adjusted_era5_monthly_norms(55.75, 37.62)
        self.assertEqual(len(moscow_norms), 12)
        jul_m = moscow_norms[6]
        jan_m = moscow_norms[0]
        self.assertTrue(jul_m["temp_max"] > jan_m["temp_max"])
        self.assertTrue(jul_m["temp_max"] < 35)

        # 2. Subtropical/Equatorial (Miami lat=25.8) - must not blow up into 60-90°C!
        miami_norms = get_adjusted_era5_monthly_norms(25.8, -80.2)
        for m in miami_norms:
            self.assertLessEqual(m["temp_max"], 48, f"Unrealistic high temp in Miami: {m}")
            self.assertGreaterEqual(m["temp_min"], -20, f"Unrealistic low temp in Miami: {m}")

        # 3. Southern Hemisphere (Sydney lat=-33.8) - seasons reversed: Jan is summer, Jul is winter!
        sydney_norms = get_adjusted_era5_monthly_norms(-33.8, 151.2)
        syd_jan = sydney_norms[0]  # January (Summer)
        syd_jul = sydney_norms[6]  # July (Winter)
        self.assertGreater(syd_jan["temp_max"], syd_jul["temp_max"], "January should be warmer than July in Sydney!")

    def test_i18n_climate_strings_with_unit(self):
        # Default unit is °C when not specified
        txt_c_default = t("climate_above_norm", val=2.5)
        self.assertIn("°C", txt_c_default)
        self.assertIn("+2.5", txt_c_default)

        # Explicit unit °F
        txt_f = t("climate_above_norm", val=4.5, unit="°F")
        self.assertIn("°F", txt_f)
        self.assertIn("+4.5", txt_f)
        self.assertNotIn("°C", txt_f)

    def test_climate_widget_celsius_and_fahrenheit(self):
        widget = ClimateNormsWidget()
        data = WeatherForecastData(
            city_name="Test City",
            lat=55.75,
            lon=37.62,
            current=CurrentConditions(temp=20.0),
        )

        # Celsius mode
        widget.update_climate_data(data, lang="ru", temp_unit="celsius")
        self.assertIn("+20°", widget.lbl_fact_val.text())
        self.assertIn("°C", widget.lbl_anom_val.text())
        self.assertEqual(widget.table_layout.count(), 13)

        # Fahrenheit mode: 20°C should display as +68° and anomaly with °F
        widget.update_climate_data(data, lang="ru", temp_unit="fahrenheit")
        self.assertIn("+68°", widget.lbl_fact_val.text())
        self.assertIn("°F", widget.lbl_anom_val.text())
        self.assertNotIn("°C", widget.lbl_anom_val.text())

    @patch("core.geomagnetic.fetch_geomagnetic_activity_async")
    @patch("core.geomagnetic.fetch_geomagnetic_forecast_async")
    def test_detailed_dialog_glanceable_metric_conversion(self, mock_f, mock_a):
        tmp_dir = tempfile.mkdtemp()
        cfg = ConfigManager(config_path=Path(tmp_dir) / "config.json")
        cfg.set("units", {"temp": "F"})

        data = WeatherForecastData(
            city_name="Test City",
            lat=55.75,
            lon=37.62,
            current=CurrentConditions(temp=20.0, condition_text="Ясно"),
        )

        dlg = DetailedForecastDialogQt(parent=None, config_manager=cfg, data=data)
        # Tab 0 glanceable metric should display 20°C as +68°F (not +20°F!)
        t0_metric = dlg.tabs[0].lbl_metric.text()
        self.assertIn("+68°F", t0_metric)
        self.assertNotIn("+20°F", t0_metric)

        # Summary line at the bottom should show +68°F
        self.assertIn("+68°F", dlg.lbl_cond_summary.text())

        # Climate widget tab should receive temp_unit="fahrenheit"
        self.assertIn("+68°", dlg.climate_widget.lbl_fact_val.text())
        self.assertIn("°F", dlg.climate_widget.lbl_anom_val.text())

        dlg.close()


if __name__ == "__main__":
    unittest.main()
