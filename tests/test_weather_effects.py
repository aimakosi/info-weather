"""Unit tests for procedural weather effects layer."""

import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from ui.qt_compat import QApplication, QPixmap, QtCore  # noqa: E402

app = QApplication.instance()
if app is None:
    app = QApplication([])

# Qt widgets below need an existing QApplication instance (created above)
from ui.effects.weather_effects import (  # noqa: E402
    WeatherEffectsCanvas,
    resolve_effect_from_wmo,
)


class TestWeatherEffects(unittest.TestCase):
    def test_wmo_resolution(self):
        self.assertEqual(resolve_effect_from_wmo(0, is_day=True), "sun_rays")
        self.assertEqual(resolve_effect_from_wmo(0, is_day=False), "none")
        self.assertEqual(resolve_effect_from_wmo(3), "clouds")
        self.assertEqual(resolve_effect_from_wmo(45), "fog")
        self.assertEqual(resolve_effect_from_wmo(51), "drizzle")
        self.assertEqual(resolve_effect_from_wmo(61), "rain")
        self.assertEqual(resolve_effect_from_wmo(71, wind_speed=3.0), "snow")
        self.assertEqual(resolve_effect_from_wmo(71, wind_speed=8.5), "blizzard")
        self.assertEqual(resolve_effect_from_wmo(66), "sleet")
        self.assertEqual(resolve_effect_from_wmo(95), "thunderstorm")

    def test_canvas_renders_all_effects(self):
        canvas = WeatherEffectsCanvas()
        canvas.resize(460, 280)

        effects = [
            "none",
            "rain",
            "drizzle",
            "snow",
            "sleet",
            "blizzard",
            "thunderstorm",
            "fog",
            "sun_rays",
            "clouds",
        ]

        pix = QPixmap(460, 280)

        for eff in effects:
            for is_light in (True, False):
                canvas.set_effect(
                    effect_name=eff,
                    wind_deg=135.0,
                    wind_spd=4.5,
                    is_light=is_light,
                    animation_mode="balanced",
                )
                canvas._on_tick()
                pix.fill(QtCore.Qt.GlobalColor.transparent)
                canvas.render(pix)
                self.assertFalse(pix.isNull())

    def test_power_saver_stops_timer(self):
        canvas = WeatherEffectsCanvas()
        canvas.resize(460, 280)
        canvas.set_effect("rain", animation_mode="power_saver")
        self.assertFalse(canvas._timer.isActive())

        canvas.set_effect("rain", animation_mode="balanced")
        self.assertTrue(canvas._timer.isActive())

        canvas.set_effect("none", animation_mode="balanced")
        self.assertFalse(canvas._timer.isActive())


if __name__ == "__main__":
    unittest.main()
