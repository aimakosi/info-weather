"""Unit tests for PySide6 / Qt UI components."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

# Enable offscreen rendering for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from ui.qt_compat import (
    QApplication,
    QCheckBox,
    QFont,
    QMouseEvent,
    QPixmap,
    QPushButton,
    QSizePolicy,
    Qt,
    QtCore,
    QWidget,
)

# Ensure QApplication singleton exists for tests
app = QApplication.instance()
if app is None:
    app = QApplication(["test_qt_ui"])

# Qt widgets below need an existing QApplication instance (created above)
from core.config import ConfigManager  # noqa: E402
from core.i18n import t  # noqa: E402
from models.weather import (  # noqa: E402
    CurrentConditions,
    DailyForecast,
    DayDetailedForecast,
    WeatherForecastData,
)
from ui.blocks import (  # noqa: E402
    AdditionalInfoBlockWidget,
    AstronomyBlockWidget,
    DailyBlockWidget,
    DayPeriodsBlockWidget,
    HeaderBlockWidget,
    WindBlockWidget,
)
from ui.dialogs import CitySearchDialogQt, DetailedForecastDialogQt, SettingsDialogQt  # noqa: E402
from ui.widget_window import WeatherWidgetWindowQt  # noqa: E402


def make_test_weather_data() -> WeatherForecastData:
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
        condition_text="Пасмурно",
        weather_code=3,
        is_day=1,
    )
    daily = [
        DailyForecast(day="Чт", weekday_idx=3, min=-1.0, max=2.0, code=3, icon_name="weather-clouds", precip_prob_max=10, date_str="2026-10-15"),
        DailyForecast(day="Пт", weekday_idx=4, min=-2.0, max=3.0, code=71, icon_name="weather-snow", precip_prob_max=60, date_str="2026-10-16"),
        DailyForecast(day="Сб", weekday_idx=5, min=-3.0, max=2.0, code=61, icon_name="weather-rain", precip_prob_max=50, date_str="2026-10-17"),
        DailyForecast(day="Вс", weekday_idx=6, min=-1.0, max=3.0, code=61, icon_name="weather-rain", precip_prob_max=40, date_str="2026-10-18"),
        DailyForecast(day="Пн", weekday_idx=0, min=-2.0, max=5.0, code=3, icon_name="weather-clouds", precip_prob_max=15, date_str="2026-10-19"),
        DailyForecast(day="Вт", weekday_idx=1, min=2.0, max=11.0, code=61, icon_name="weather-rain", precip_prob_max=70, date_str="2026-10-20"),
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
            hourly_winds=[2.0] * 24,
            hourly_wind_dirs=[270] * 24,
            hourly_codes=[71] * 24,
            hourly_is_days=[0 if h < 6 or h > 18 else 1 for h in range(24)],
            wind_max=4.0,
            dominant_wind_cardinal="W",
        ),
    ]
    return WeatherForecastData(
        city_name="Абакан",
        country="RU",
        lat=53.72,
        lon=91.44,
        current=current,
        daily=daily,
        days_detailed=days_det,
    )


class TestQtUIBlocks(unittest.TestCase):
    def setUp(self):
        self.data = make_test_weather_data()

    def test_header_block(self):
        widget = HeaderBlockWidget()
        widget.update(self.data)
        self.assertEqual(widget.lbl_city.text(), "Абакан")
        self.assertIn("1°", widget.lbl_temp.text())
        self.assertEqual(widget.lbl_cond.text(), "Пасмурно")

    def test_header_block_localized(self):
        # English
        widget_en = HeaderBlockWidget(options={"lang": "en"})
        widget_en.update(self.data)
        self.assertEqual(widget_en.lbl_city.text(), "Abakan")
        self.assertEqual(widget_en.lbl_cond.text(), "Overcast")

        # Ukrainian
        widget_uk = HeaderBlockWidget(options={"lang": "uk"})
        widget_uk.update(self.data)
        self.assertEqual(widget_uk.lbl_city.text(), "Абакан")
        self.assertEqual(widget_uk.lbl_cond.text(), "Похмуро")

        # Moscow in English
        moscow_data = make_test_weather_data()
        moscow_data.city_name = "Москва"
        moscow_data.lat = 55.75
        moscow_data.lon = 37.61
        moscow_data.country = "Россия"
        widget_en.update(moscow_data)
        self.assertEqual(widget_en.lbl_city.text(), "Moscow")

    def test_daily_block(self):
        widget = DailyBlockWidget(options={"days": 5, "horizontal": True})
        widget.update(self.data)
        self.assertEqual(len(widget.rows), 5)
        self.assertTrue(widget.horizontal)
        from ui.qt_compat import QHBoxLayout
        self.assertIsInstance(widget.main_layout, QHBoxLayout)
        for row in widget.rows:
            self.assertGreaterEqual(row["container"].minimumWidth(), 80)
            # Day columns have a fixed width and wrap condition text by words
            self.assertEqual(
                row["container"].minimumWidth(),
                row["container"].maximumWidth(),
            )
            self.assertTrue(row["cond_label"].wordWrap())
            self.assertEqual(
                row["cond_label"].minimumWidth(),
                row["cond_label"].maximumWidth(),
            )
            self.assertGreaterEqual(row["container"].minimumHeight(), 68)
            self.assertGreaterEqual(row["cond_label"].minimumHeight(), 18)
        # First row should be next day (Fri, 16.10)
        row0 = widget.rows[0]
        self.assertIn("Пт", row0["day_label"].text())
        self.assertIn("3°", row0["max_label"].text())
        self.assertIn("-2°", row0["min_label"].text())

    def test_daily_block_weekend_and_small_font(self):
        widget = DailyBlockWidget(options={
            "days": 5,
            "horizontal": True,
            "weekend": "Fr, Sa",
            "weekend_color": "#00ff00",
            "small_font_family": "Test Small Font",
            "small_font_size": 9,
        })
        widget.update(self.data)
        # Fri (row 0) and Sat (row 1) are weekends for this definition
        self.assertIn("#00ff00", widget.rows[0]["day_label"].styleSheet())
        self.assertIn("#00ff00", widget.rows[1]["day_label"].styleSheet())
        # Sun (row 2) is not a weekend in "Fr, Sa"
        self.assertNotIn("#00ff00", widget.rows[2]["day_label"].styleSheet())
        self.assertEqual(widget.rows[0]["day_label"].font().family(), "Test Small Font")

    def test_date_format_in_header_and_daily(self):
        header = HeaderBlockWidget(options={"lang": "ru", "date_format": "YYYY-MM-DD"})
        header.update(self.data)
        self.assertEqual(header.lbl_date.text(), "Чт, 2026-10-15")

        daily = DailyBlockWidget(options={"days": 5, "date_format": "YYYY-MM-DD"})
        daily.update(self.data)
        self.assertEqual(daily.rows[0]["day_label"].text(), "Пт, 2026-10-16")

    def test_tomorrow_block_uses_small_font(self):
        widget = DayPeriodsBlockWidget(options={
            "mode": "tomorrow",
            "title": "Завтра",
            "small_font_family": "Test Small Font",
            "small_font_size": 9,
        })
        cell = widget.period_cells["night"]
        self.assertEqual(cell["name_label"].font().family(), "Test Small Font")
        self.assertEqual(cell["temp_label"].font().family(), "Test Small Font")

    def test_wind_block(self):
        widget = WindBlockWidget(options={"angle": 0, "arrow_color": "#00ff00"})
        clicked_events = []
        widget.clicked.connect(lambda: clicked_events.append(True))
        widget.update(self.data)
        self.assertEqual(widget.wind_speed, 3.0)
        self.assertEqual(widget.wind_dir, 315.0)
        self.assertIn("NW", widget.lbl_text.text())
        self.assertEqual(widget.compass.arrow_color.name(), "#00ff00")
        self.assertEqual(widget.cursor().shape(), Qt.CursorShape.PointingHandCursor)

        # Render canvas to verify 16-ray paintEvent executes cleanly
        pix = QPixmap(80, 80)
        widget.compass.render(pix)

        # Test click emission on LMB release
        press = QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, QtCore.QPointF(10, 10), QtCore.QPointF(10, 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QtCore.QEvent.Type.MouseButtonRelease, QtCore.QPointF(10, 10), QtCore.QPointF(10, 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.mousePressEvent(press)
        widget.mouseReleaseEvent(release)
        self.assertEqual(len(clicked_events), 1)

    def test_wind_block_nautical_variant1_languages_and_themes(self):
        from data.wmo_conditions import COMPASS_CARDINALS_4, COMPASS_INTERCARDINALS_4

        self.assertIn("ru", COMPASS_CARDINALS_4)
        self.assertIn("uk", COMPASS_CARDINALS_4)
        self.assertIn("en", COMPASS_CARDINALS_4)
        self.assertIn("ru", COMPASS_INTERCARDINALS_4)
        self.assertIn("uk", COMPASS_INTERCARDINALS_4)
        self.assertIn("en", COMPASS_INTERCARDINALS_4)

        for lang in ("ru", "uk", "en"):
            widget = WindBlockWidget(options={"lang": lang, "arrow_color": "#f97316"})
            widget.update(self.data)
            self.assertEqual(widget.compass.lang, lang)
            self.assertEqual(widget.compass.wind_speed, 3.0)

            # Test dark render
            pix_dark = QPixmap(136, 98)
            pix_dark.fill(Qt.GlobalColor.transparent)
            widget.compass.render(pix_dark)
            self.assertFalse(pix_dark.isNull())

            # Test light theme render
            widget.setProperty("class", "light-theme")
            pix_light = QPixmap(136, 98)
            pix_light.fill(Qt.GlobalColor.transparent)
            widget.compass.render(pix_light)
            self.assertFalse(pix_light.isNull())

    def test_day_periods_block(self):
        widget = DayPeriodsBlockWidget(options={"mode": "tomorrow", "title": "Завтра"})
        widget.update(self.data)
        self.assertEqual(widget.lbl_title.text(), "Завтра")
        self.assertIn("night", widget.period_cells)
        self.assertIn("day", widget.period_cells)

    def test_additional_info_block(self):
        widget = AdditionalInfoBlockWidget()
        widget.update(self.data)
        self.assertIn("748 мм", widget.press_row["val_label"].text())
        self.assertIn("75% влажн.", widget.hum_row["val_label"].text())
        self.assertIn("Т. росы: -3°", widget.extra_row["val_label"].text())

    def test_additional_info_block_localized(self):
        widget = AdditionalInfoBlockWidget(options={
            "lang": "en",
            "wind_unit": "m/s",
            "temp_unit": "celsius",
            "pressure_unit": "hPa",
        })
        widget.update(self.data)
        self.assertIn("3 m/s", widget.wind_row["val_label"].text())
        self.assertIn("NW", widget.wind_row["val_label"].text())
        self.assertEqual(widget.press_row["val_label"].text(), "997 hPa")
        self.assertIn("75% hum.", widget.hum_row["val_label"].text())
        self.assertIn("Dew point: -3°", widget.extra_row["val_label"].text())

        widget_uk = AdditionalInfoBlockWidget(options={
            "lang": "uk",
            "wind_unit": "m/s",
            "temp_unit": "celsius",
            "pressure_unit": "mmHg",
        })
        widget_uk.update(self.data)
        self.assertIn("волог.", widget_uk.hum_row["val_label"].text())
        self.assertIn("Т. роси", widget_uk.extra_row["val_label"].text())

    def test_service_icon_rendering_is_visible(self):
        from ui.utils import render_colored_icon

        for color in ("#cbd5e1", "#334155"):
            pix = render_colored_icon("wind.svg", 16, color)
            self.assertFalse(pix.isNull())
            image = pix.toImage()
            has_pixels = any(
                image.pixelColor(x, y).alpha() > 0
                for y in range(image.height())
                for x in range(image.width())
            )
            self.assertTrue(has_pixels)

    def test_astronomy_block(self):
        widget = AstronomyBlockWidget()
        widget.update(self.data)
        self.assertTrue(len(widget.sunrise_item["val_label"].text()) > 0)
        self.assertTrue(len(widget.sunset_item["val_label"].text()) > 0)
        self.assertTrue(len(widget.duration_item["val_label"].text()) > 0)
        self.assertRegex(widget.duration_item["val_label"].text(), r"^\d{2}:\d{2}$")
        self.assertNotEqual(widget.duration_item["val_label"].text(), "00:00")

    def test_astronomy_block_compact_and_distinct_icons(self):
        widget = AstronomyBlockWidget(options={"show_moon": True}, scale=1.0)
        self.assertEqual(
            widget.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Maximum,
        )
        self.assertTrue(widget.layout.alignment() & Qt.AlignmentFlag.AlignLeft)

        widget.update(self.data)
        for item in (widget.sunrise_item, widget.sunset_item, widget.duration_item):
            self.assertFalse(item["icon_label"].pixmap().isNull())
        # Moon icon is generated dynamically from the phase
        self.assertFalse(widget.moon_item["icon_label"].pixmap().isNull())

        from ui.utils import get_weather_icon_path
        paths = {
            get_weather_icon_path(name)
            for name in ("sunrise.svg", "sunset.svg", "sun.svg")
        }
        self.assertEqual(len(paths), 3)

    def test_astronomy_block_tooltips_localized(self):
        for lang, expected_sr, expected_ss, expected_dl, expected_moon in (
            ("ru", "Восход:", "Закат:", "Долгота дня:", "Луна:"),
            ("uk", "Схід:", "Захід:", "Тривалість дня:", "Місяць:"),
            ("en", "Sunrise:", "Sunset:", "Daylight duration:", "Moon:"),
        ):
            widget = AstronomyBlockWidget(options={"lang": lang, "show_moon": True})
            widget.update(self.data)
            self.assertTrue(widget.sunrise_item["container"].toolTip().startswith(expected_sr), f"Failed for {lang}: {widget.sunrise_item['container'].toolTip()}")
            self.assertTrue(widget.sunset_item["container"].toolTip().startswith(expected_ss), f"Failed for {lang}: {widget.sunset_item['container'].toolTip()}")
            self.assertTrue(widget.duration_item["container"].toolTip().startswith(expected_dl), f"Failed for {lang}: {widget.duration_item['container'].toolTip()}")
            self.assertTrue(widget.moon_item["container"].toolTip().startswith(expected_moon), f"Failed for {lang}: {widget.moon_item['container'].toolTip()}")


class TestQtDialogsAndWidgetWindow(unittest.TestCase):
    def setUp(self):
        self.data = make_test_weather_data()
        # Never touch the real user config: use a throwaway one per test
        self._tmp_dir = tempfile.mkdtemp(prefix="info_weather_qt_test_")
        self.cfg = ConfigManager(Path(self._tmp_dir) / "config.json")
        self.cfg.set("app_language", "ru")
        self.cfg.set("weather_language", "ru")
        self.provider = MagicMock()
        self.provider.get_active_city_info.return_value = {
            "name": "Абакан",
            "lat": 53.72,
            "lon": 91.44,
            "country": "RU",
        }

    def tearDown(self):
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_settings_dialog(self):
        changed = []
        dlg = SettingsDialogQt(parent=None, config_manager=self.cfg, on_config_changed=lambda: changed.append(True))
        self.assertIsNotNone(dlg.combo_icons)
        self.assertEqual(dlg.tabs.count(), 6)
        self.assertEqual(dlg.tabs.tabText(0), t("tab_general"))
        for i in range(6):
            self.assertEqual(dlg.tabs.widget(i).objectName(), "TabScroll")

        # Test theme synchronization
        self.cfg.set("skin", {"theme_mode": "day"})
        dlg._apply_theme()
        self.assertEqual(dlg.property("theme"), "light")
        for scroll, container in dlg._tab_pages:
            self.assertEqual(container.property("theme"), "light")

        self.cfg.set("skin", {"theme_mode": "night"})
        dlg._apply_theme()
        self.assertEqual(dlg.property("theme"), "dark")
        for scroll, container in dlg._tab_pages:
            self.assertEqual(container.property("theme"), "dark")

        # Select another icon theme
        count = dlg.combo_icons.count()
        self.assertGreater(count, 1)
        curr = dlg.combo_icons.currentIndex()
        new_idx = (curr + 1) % count
        dlg.combo_icons.setCurrentIndex(new_idx)
        self.assertTrue(len(changed) >= 1)

        # Check language selectors on General tab
        self.assertIsNotNone(dlg.combo_app_lang)
        self.assertEqual(dlg.combo_app_lang.count(), 3)
        self.assertEqual([dlg.combo_app_lang.itemData(i) for i in range(3)], ["en", "uk", "ru"])
        self.assertIsNotNone(dlg.combo_weather_lang)
        self.assertEqual(dlg.combo_weather_lang.count(), 3)
        self.assertEqual([dlg.combo_weather_lang.itemData(i) for i in range(3)], ["en", "uk", "ru"])

        # Switch weather language to Ukrainian
        dlg.combo_weather_lang.setCurrentIndex(1)
        self.assertEqual(self.cfg.get("weather_language"), "uk")

        # Switch app language to Ukrainian
        dlg.combo_app_lang.setCurrentIndex(1)
        self.assertEqual(self.cfg.get("app_language"), "uk")
        self.assertEqual(dlg.tabs.tabText(0), "Загальні")
        self.assertEqual(dlg.windowTitle(), "Налаштування — Info Weather")

        # Switch app language to English
        dlg.combo_app_lang.setCurrentIndex(0)
        self.assertEqual(self.cfg.get("app_language"), "en")
        self.assertEqual(dlg.tabs.tabText(0), "General")
        self.assertEqual(dlg.tabs.tabText(1), "Appearance")
        # Check launch mode on Appearance tab
        self.assertIsNotNone(dlg.combo_launch_mode)
        self.assertEqual(dlg.combo_launch_mode.count(), 3)
        self.assertEqual([dlg.combo_launch_mode.itemData(i) for i in range(3)], ["both", "widget_only", "indicator_only"])
        dlg.combo_launch_mode.setCurrentIndex(1)  # widget_only
        self.assertEqual(self.cfg.get("display_mode"), "widget_only")
        dlg.combo_launch_mode.setCurrentIndex(2)  # indicator_only
        self.assertEqual(self.cfg.get("display_mode"), "indicator_only")
        dlg.combo_launch_mode.setCurrentIndex(0)  # both
        self.assertEqual(self.cfg.get("display_mode"), "both")

        dlg.close()
    def test_appearance_tab_new_settings(self):
        changed = []
        dlg = SettingsDialogQt(parent=None, config_manager=self.cfg, on_config_changed=lambda: changed.append(True))
        self.assertIsNotNone(dlg.combo_font_main)
        self.assertIsNotNone(dlg.combo_font_small)
        self.assertIsNotNone(dlg.edit_weekend)
        self.assertIsNotNone(dlg.btn_weekend_color)
        self.assertEqual(dlg.edit_weekend.text(), "Sa, Su")

        # Main and small font selection are persisted separately
        if dlg.combo_font_main.count() > 1:
            main_idx = (dlg.combo_font_main.currentIndex() + 1) % dlg.combo_font_main.count()
            dlg.combo_font_main.setCurrentIndex(main_idx)
            self.assertEqual(
                self.cfg.get("skin")["font_family"],
                dlg._font_family(dlg.combo_font_main.currentFont()),
            )
        else:
            dlg._on_main_font_changed(QFont("Sans Serif"))
            self.assertEqual(self.cfg.get("skin")["font_family"], "Sans Serif")

        if dlg.combo_font_small.count() > 1:
            small_idx = (dlg.combo_font_small.currentIndex() + 1) % dlg.combo_font_small.count()
            dlg.combo_font_small.setCurrentIndex(small_idx)
            self.assertEqual(
                self.cfg.get("skin")["small_font_family"],
                dlg._font_family(dlg.combo_font_small.currentFont()),
            )
        else:
            dlg._on_small_font_changed(QFont("Monospace"))
            self.assertEqual(self.cfg.get("skin")["small_font_family"], "Monospace")

        # Weekend day definition and color
        dlg.edit_weekend.setText("Fr, Sa")
        dlg.edit_weekend.editingFinished.emit()
        self.assertEqual(self.cfg.get("formats")["weekend"], "Fr, Sa")

        dlg._set_weekend_color("#00ff00")
        self.assertEqual(self.cfg.get("skin")["weekend_color"], "#00ff00")
        self.assertEqual(dlg.btn_weekend_color.text(), "#00ff00")

        # Per-row reset buttons restore defaults
        dlg._reset_weekend()
        self.assertEqual(self.cfg.get("formats")["weekend"], "Sa, Su")
        self.assertEqual(dlg.edit_weekend.text(), "Sa, Su")
        dlg._reset_weekend_color()
        self.assertEqual(self.cfg.get("skin")["weekend_color"], "#ef4444")
        dlg._reset_main_font()
        self.assertEqual(self.cfg.get("skin")["font_family"], "Serif")
        dlg._reset_small_font()
        self.assertEqual(self.cfg.get("skin")["small_font_family"], "Serif")

        # Wind rose arrow color
        self.assertIsNotNone(dlg.btn_wind_color)
        dlg._set_wind_color("#00ff00")
        self.assertEqual(self.cfg.get("skin")["wind_arrow_color"], "#00ff00")
        dlg._reset_wind_color()
        self.assertEqual(self.cfg.get("skin")["wind_arrow_color"], "#ef4444")
        self.assertTrue(len(changed) >= 5)

        # auto_system follows the KDE/Qt Application Style color scheme
        from unittest.mock import patch
        skin = dict(self.cfg.get("skin"))
        skin["theme_mode"] = "auto_system"
        self.cfg.set("skin", skin)
        with patch("ui.dialogs.settings_dialog.is_system_light_theme", return_value=True):
            dlg._apply_theme()
            self.assertEqual(dlg.property("theme"), "light")
        with patch("ui.dialogs.settings_dialog.is_system_light_theme", return_value=False):
            dlg._apply_theme()
            self.assertEqual(dlg.property("theme"), "dark")

        dlg.close()

    def test_theme_mode_options(self):
        skin = dict(self.cfg.get("skin"))
        skin["theme_mode"] = "auto_system"
        self.cfg.set("skin", skin)

        dlg = SettingsDialogQt(parent=None, config_manager=self.cfg)
        self.assertIsNotNone(dlg.combo_mode)
        item_data = [dlg.combo_mode.itemData(i) for i in range(dlg.combo_mode.count())]
        self.assertEqual(item_data, ["auto_solar", "day", "night"])
        self.assertNotIn("auto_system", item_data)
        self.assertEqual(dlg.combo_mode.currentData(), "auto_solar")

        idx_night = dlg.combo_mode.findData("night")
        dlg.combo_mode.setCurrentIndex(idx_night)
        self.assertEqual(self.cfg.get("skin")["theme_mode"], "night")
        dlg.close()

    def test_units_date_format_setting(self):
        dlg = SettingsDialogQt(parent=None, config_manager=self.cfg)
        self.assertIsNotNone(dlg.combo_date_format)
        self.assertEqual(dlg.combo_date_format.currentData(), "DD.MM")

        idx = dlg.combo_date_format.findData("YYYY-MM-DD")
        self.assertGreaterEqual(idx, 0)
        dlg.combo_date_format.setCurrentIndex(idx)
        self.assertEqual(self.cfg.get("formats")["date_format"], "YYYY-MM-DD")
        dlg.close()
    def test_layout_window_behavior_settings(self):
        dlg = SettingsDialogQt(parent=None, config_manager=self.cfg)
        self.assertIsNotNone(dlg.chk_lock_position)
        self.assertIsNotNone(dlg.chk_on_all_desktops)
        self.assertIsNotNone(dlg.chk_always_on_top)
        self.assertIsNotNone(dlg.chk_show_in_taskbar)
        self.assertFalse(dlg.chk_lock_position.isChecked())
        self.assertFalse(dlg.chk_show_in_taskbar.isChecked())

        dlg.chk_lock_position.setChecked(True)
        dlg.chk_always_on_top.setChecked(True)
        dlg.chk_show_in_taskbar.setChecked(True)
        behavior = self.cfg.get("window_behavior")
        self.assertTrue(behavior["lock_position"])
        self.assertTrue(behavior["always_on_top"])
        self.assertFalse(behavior["on_all_desktops"])
        self.assertTrue(behavior["show_in_taskbar"])

        dlg.chk_lock_position.setChecked(False)
        dlg.chk_always_on_top.setChecked(False)
        dlg.chk_show_in_taskbar.setChecked(False)
        self.assertFalse(self.cfg.get("window_behavior")["lock_position"])
        self.assertFalse(self.cfg.get("window_behavior")["always_on_top"])
        self.assertFalse(self.cfg.get("window_behavior")["show_in_taskbar"])
        dlg.close()
    def test_provider_network_settings(self):
        changed = []
        dlg = SettingsDialogQt(parent=None, config_manager=self.cfg, on_config_changed=lambda: changed.append(True))

        self.assertIsNotNone(dlg.spin_net_timeout)
        self.assertIsNotNone(dlg.spin_net_dns)
        self.assertIsNotNone(dlg.spin_net_retries)
        self.assertIsNotNone(dlg.spin_net_fetch)
        self.assertIsNotNone(dlg.chk_prefer_ipv4)
        self.assertEqual(dlg.spin_net_timeout.value(), 8.0)
        self.assertEqual(dlg.spin_net_dns.value(), 5.0)
        self.assertEqual(dlg.spin_net_retries.value(), 1)
        self.assertEqual(dlg.spin_net_fetch.value(), 30.0)
        self.assertTrue(dlg.chk_prefer_ipv4.isChecked())

        dlg.spin_net_timeout.setValue(4.5)
        dlg.spin_net_dns.setValue(0.0)
        dlg.spin_net_retries.setValue(3)
        dlg.spin_net_fetch.setValue(45.0)
        dlg.chk_prefer_ipv4.setChecked(False)
        self.assertTrue(len(changed) >= 5)

        network = self.cfg.get("network")
        self.assertEqual(network["timeout_seconds"], 4.5)
        self.assertEqual(network["dns_timeout_seconds"], 0.0)
        self.assertEqual(network["retries"], 3)
        self.assertEqual(network["fetch_timeout_seconds"], 45.0)
        self.assertFalse(network["prefer_ipv4"])

        dlg.close()
    def test_city_search_dialog(self):
        changed_city = []
        dlg = CitySearchDialogQt(
            parent=None,
            config_manager=self.cfg,
            weather_provider=self.provider,
            on_city_changed=lambda c: changed_city.append(c),
        )
        self.assertIsNotNone(dlg.search_edit)
        # Test adding city directly
        new_city = {"name": "TestCity", "lat": 10.0, "lon": 20.0, "country": "TC"}
        dlg._add_city(new_city)
        cities = self.cfg.get("cities", [])
        self.assertTrue(any(c["name"] == "TestCity" for c in cities))

        # Test search results layout with long city name (BtnAddCity and BtnSelectCity must not overflow)
        from providers.base import SearchResult
        results = [
            SearchResult(name="Saint Petersburg", country="Russian Federation", admin1="Northwestern Federal District", lat=59.94, lon=30.31),
        ]
        dlg.show()
        dlg._display_search_results("", results)
        app.processEvents()

        row = dlg.results_layout.itemAt(0).widget()
        self.assertIsNotNone(row)
        btn_add = row.findChild(QPushButton, "BtnAddCity")
        btn_sel = row.findChild(QPushButton, "BtnSelectCity")
        self.assertIsNotNone(btn_add)
        self.assertIsNotNone(btn_sel)
        self.assertLessEqual(btn_add.x() + btn_add.width(), row.width())
        self.assertLessEqual(btn_sel.x() + btn_sel.width(), row.width())

        dlg.close()
    def test_city_search_dialog_theme_and_retranslate(self):
        # 1. Night theme
        skin = dict(self.cfg.get("skin", {}))
        skin["theme_mode"] = "night"
        self.cfg.set("skin", skin)

        dlg = CitySearchDialogQt(
            parent=None,
            config_manager=self.cfg,
            weather_provider=self.provider,
        )
        self.assertFalse(dlg._is_light_theme())
        self.assertEqual(dlg.property("theme"), "dark")
        self.assertIn("#0f172a", dlg.styleSheet())
        self.assertIn("BtnSelectCity", dlg.styleSheet())

        # 2. Day theme
        skin["theme_mode"] = "day"
        self.cfg.set("skin", skin)
        dlg._apply_theme()
        self.assertTrue(dlg._is_light_theme())
        self.assertEqual(dlg.property("theme"), "light")
        self.assertIn("#f8fafc", dlg.styleSheet())

        # 3. Retranslate UI
        dlg.retranslate_ui()
        self.assertIsNotNone(dlg.windowTitle())
        dlg.close()

    def test_saved_locations_button_alignment(self):
        cities = [
            {"name": "CityA", "lat": 10.0, "lon": 10.0},
            {"name": "CityB", "lat": 20.0, "lon": 20.0},
            {"name": "CityC", "lat": 30.0, "lon": 30.0},
        ]
        self.cfg.set("cities", cities)
        self.cfg.set("home_city", "CityA")
        self.cfg.set("current_city", "CityA")

        dlg = CitySearchDialogQt(
            parent=None,
            config_manager=self.cfg,
            weather_provider=self.provider,
        )
        dlg.resize(600, 500)
        dlg.show()
        app.processEvents()

        row0 = dlg.cities_layout.itemAt(0).widget()
        row1 = dlg.cities_layout.itemAt(1).widget()
        row2 = dlg.cities_layout.itemAt(2).widget()

        self.assertIsNotNone(row0.findChild(QWidget, "SpacerUpCity"))
        self.assertIsNotNone(row0.findChild(QPushButton, "BtnDownCity"))
        self.assertIsNone(row0.findChild(QPushButton, "BtnUpCity"))

        self.assertIsNotNone(row1.findChild(QPushButton, "BtnUpCity"))
        self.assertIsNotNone(row1.findChild(QPushButton, "BtnDownCity"))

        self.assertIsNotNone(row2.findChild(QWidget, "SpacerDownCity"))
        self.assertIsNotNone(row2.findChild(QPushButton, "BtnUpCity"))
        self.assertIsNone(row2.findChild(QPushButton, "BtnDownCity"))

        # Row 1 and Row 2 both have Select and Home buttons: their x-positions must align
        btn_sel1 = row1.findChild(QPushButton, "BtnSelectCity")
        btn_sel2 = row2.findChild(QPushButton, "BtnSelectCity")
        btn_home1 = row1.findChild(QPushButton, "BtnHomeCity")
        btn_home2 = row2.findChild(QPushButton, "BtnHomeCity")
        self.assertEqual(btn_sel1.x(), btn_sel2.x())
        self.assertEqual(btn_home1.x(), btn_home2.x())

        dlg.close()
        dlg.deleteLater()
        app.processEvents()

    def test_weather_widget_window(self):
        # Deterministic theme for the gradient assertions below
        skin = dict(self.cfg.get("skin"))
        skin["theme_mode"] = "night"
        self.cfg.set("skin", skin)

        window = WeatherWidgetWindowQt(provider=self.provider, config_manager=self.cfg)
        self.assertIsNotNone(window.container)
        self.assertGreater(len(window.blocks), 0)
        # Check minimum width is at least 480px for horizontal Gis-Weather layout
        self.assertGreaterEqual(window.container.minimumWidth(), 480)
        self.assertGreaterEqual(window.minimumWidth(), 500)

        # Trigger data update
        window._on_weather_updated_main_thread(self.data)
        self.assertEqual(window._last_data.city_name, "Абакан")
        self.assertIn("qlineargradient", window.container.styleSheet())
        self.assertIn("rgba(16, 19, 24", window.container.styleSheet())

        # Test language update
        self.cfg.set("weather_language", "uk")
        window._on_config_changed()
        self.assertEqual(window.provider.lang, "uk")

        # Test display mode update
        self.cfg.set("display_mode", "widget_only")
        window._on_config_changed()
        self.assertFalse(window.tray.isVisible())

        self.cfg.set("display_mode", "both")
        window._on_config_changed()
        self.assertTrue(window.tray.isVisible())

        window.close()

    def test_widget_appearance_options(self):
        skin = dict(self.cfg.get("skin"))
        skin.update({
            "theme_mode": "night",
            "font_family": "Test Main Font",
            "small_font_family": "Test Small Font",
            "weekend_color": "#123456",
        })
        self.cfg.set("skin", skin)
        formats = dict(self.cfg.get("formats"))
        formats["weekend"] = "Fr, Sa"
        self.cfg.set("formats", formats)

        window = WeatherWidgetWindowQt(provider=self.provider, config_manager=self.cfg)
        self.assertEqual(window.container.font().family(), "Test Main Font")

        window._on_weather_updated_main_thread(self.data)
        daily = next(b for b in window.blocks if isinstance(b, DailyBlockWidget))
        self.assertEqual(daily.options["weekend"], "Fr, Sa")
        self.assertEqual(daily.options["weekend_color"], "#123456")
        self.assertEqual(daily.options["small_font_family"], "Test Small Font")
        # Friday (row 0) is a weekend day and uses the configured color/font
        self.assertIn("#123456", daily.rows[0]["day_label"].styleSheet())
        self.assertEqual(daily.rows[0]["day_label"].font().family(), "Test Small Font")

        tomorrow = next(
            b for b in window.blocks
            if isinstance(b, DayPeriodsBlockWidget) and b.mode == "tomorrow"
        )
        self.assertEqual(
            tomorrow.period_cells["night"]["name_label"].font().family(),
            "Test Small Font",
        )

        # auto_system follows KDE / Qt Application Style color scheme
        from unittest.mock import patch
        skin = dict(self.cfg.get("skin"))
        skin["theme_mode"] = "auto_system"
        self.cfg.set("skin", skin)
        with patch("ui.widget_window.is_system_light_theme", return_value=True):
            window._apply_theme()
            self.assertIn("rgba(196, 228, 252", window.container.styleSheet())
        with patch("ui.widget_window.is_system_light_theme", return_value=False):
            window._apply_theme()
            self.assertIn("rgba(16, 19, 24", window.container.styleSheet())

        window.close()

    def test_window_position_save_and_restore(self):
        window = WeatherWidgetWindowQt(provider=self.provider, config_manager=self.cfg)
        window.show()
        QApplication.processEvents()
        window.move(120, 80)
        window._save_window_position()

        saved = self.cfg.get("window_position")
        self.assertTrue(saved["saved"])
        self.assertEqual((saved["x"], saved["y"]), (120, 80))
        window.close()

        restored = WeatherWidgetWindowQt(provider=self.provider, config_manager=self.cfg)
        self.assertTrue(restored.restore_saved_position())
        self.assertEqual((restored.x(), restored.y()), (120, 80))
        restored.close()

    def test_widget_window_behavior(self):
        self.cfg.set("window_behavior", {
            "lock_position": True,
            "on_all_desktops": False,
            "always_on_top": True,
        })
        window = WeatherWidgetWindowQt(provider=self.provider, config_manager=self.cfg)
        self.assertTrue(window._lock_position)
        self.assertTrue(bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))
        # Hidden from taskbar by default (window type = Tool)
        self.assertEqual(int(window.windowFlags()) & 0xFF, int(Qt.WindowType.Tool))

        self.cfg.set("window_behavior", {
            "lock_position": False,
            "on_all_desktops": False,
            "always_on_top": False,
            "show_in_taskbar": True,
        })
        window._on_config_changed()
        self.assertFalse(window._lock_position)
        self.assertFalse(bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))
        self.assertEqual(int(window.windowFlags()) & 0xFF, int(Qt.WindowType.Window))

        self.cfg.set("window_behavior", {
            "lock_position": False,
            "on_all_desktops": False,
            "always_on_top": False,
            "show_in_taskbar": False,
        })
        window._on_config_changed()
        self.assertEqual(int(window.windowFlags()) & 0xFF, int(Qt.WindowType.Tool))
        window.close()

    def test_detailed_forecast_dialog(self):
        # 1. Direct dialog creation and page structure
        dlg = DetailedForecastDialogQt(parent=None, config_manager=self.cfg, data=self.data)
        self.assertEqual(dlg.stack.count(), 3)
        self.assertEqual(dlg.stack.currentIndex(), 0)
        self.assertIn("1/3", dlg.lbl_screen_badge.text())

        # 2. Screen switching via next_screen / LMB: 0 -> 1 -> 2 -> 0
        dlg.next_screen()
        self.assertEqual(dlg.stack.currentIndex(), 1)
        self.assertIn("2/3", dlg.lbl_screen_badge.text())

        dlg._last_switch_ts = 0.0
        dlg.next_screen()
        self.assertEqual(dlg.stack.currentIndex(), 2)
        self.assertIn("3/3", dlg.lbl_screen_badge.text())
        self.assertIn("Роза ветров", dlg.lbl_screen_badge.text())

        # Reset debounce timestamp and cycle back to 0
        dlg._last_switch_ts = 0.0
        dlg.next_screen()
        self.assertEqual(dlg.stack.currentIndex(), 0)
        self.assertIn("1/3", dlg.lbl_screen_badge.text())

        # Backward compatibility pill shim
        dlg.pill_toggle.set_index(2)
        self.assertEqual(dlg.stack.currentIndex(), 2)
        self.assertEqual(dlg.pill_toggle.current_index(), 2)
        dlg.pill_toggle.set_index(0)
        self.assertEqual(dlg.stack.currentIndex(), 0)

        # 3. Screen 1: Spline & Barometer points start from current local hour and span 24 hours
        self.assertEqual(len(dlg.spline_widget._points), 24)
        self.assertEqual(len(dlg.baro_widget._points), 24)
        utc_now = datetime.now(timezone.utc)
        offset_sec = self.data.utc_offset_seconds or 0
        expected_cur_hour = datetime.fromtimestamp(utc_now.timestamp() + offset_sec, timezone.utc).hour
        self.assertEqual(dlg.spline_widget._points[0]["time"], f"{expected_cur_hour:02d}:00")
        self.assertEqual(dlg.spline_widget._points[-1]["time"], f"{(expected_cur_hour + 23) % 24:02d}:00")
        self.assertTrue(len(dlg.lbl_tendency_pill.text()) > 0)

        # Render widgets to verify paintEvent logic and gradients execute without errors
        pix = QPixmap(600, 300)
        dlg.spline_widget.render(pix)
        dlg.baro_widget.render(pix)

        # 3b. Test 24h vs Daily tabs for Temperature & Pressure
        self.assertIsNotNone(dlg.btn_period_24h)
        self.assertIsNotNone(dlg.btn_period_daily)
        self.assertEqual(dlg._temp_press_period, "24h")
        self.assertTrue(dlg.lbl_legend_day.isHidden())
        self.assertTrue(dlg.lbl_legend_night.isHidden())

        # Switch to daily (X days)
        dlg.set_temp_press_period("daily")
        self.assertEqual(dlg._temp_press_period, "daily")
        self.assertEqual(dlg.spline_widget._mode, "daily")
        self.assertFalse(dlg.lbl_legend_day.isHidden())
        self.assertFalse(dlg.lbl_legend_night.isHidden())
        self.assertGreater(len(dlg.spline_widget._daily_points), 0)
        self.assertIn("day_temp", dlg.spline_widget._daily_points[0])
        self.assertIn("night_temp", dlg.spline_widget._daily_points[0])
        self.assertEqual(len(dlg.baro_widget._points), len(dlg.spline_widget._daily_points))

        # Render daily widgets without error
        dlg.spline_widget.render(pix)
        dlg.baro_widget.render(pix)

        # Switch back to 24h
        dlg.set_temp_press_period("24h")
        self.assertEqual(dlg._temp_press_period, "24h")
        self.assertEqual(dlg.spline_widget._mode, "hourly")
        self.assertTrue(dlg.lbl_legend_day.isHidden())

        # 4. Screen 2: ERA5 Climate Normals
        self.assertIn("Абакан", dlg.climate_widget.lbl_month_hdr.text())
        self.assertIn("ERA5", dlg.climate_widget.lbl_month_hdr.text())
        self.assertTrue(len(dlg.climate_widget.lbl_fact_val.text()) > 0)
        self.assertTrue(len(dlg.climate_widget.lbl_anom_val.text()) > 0)
        # Annual table has 12 rows (months) + 1 stretch
        self.assertEqual(dlg.climate_widget.table_layout.count(), 13)

        # 5. Screen 3: 16-Ray Stacked Wind Rose
        self.assertIsNotNone(dlg.wind_rose_widget)
        self.assertEqual(len(dlg.wind_rose_widget.buttons), 4)
        self.assertTrue(dlg.wind_rose_widget.is_interactive_control(dlg.wind_rose_widget.buttons["1h"]))
        dlg.wind_rose_widget.set_period("1h")
        self.assertEqual(dlg.wind_rose_widget._current_period, "1h")
        dlg.wind_rose_widget.set_period("8h")
        self.assertEqual(dlg.wind_rose_widget._current_period, "8h")
        dlg.wind_rose_widget.set_period("day_night")
        self.assertEqual(dlg.wind_rose_widget._current_period, "day_night")
        dlg.wind_rose_widget.set_period("24h")
        self.assertEqual(dlg.wind_rose_widget._current_period, "24h")

        # Render wind rose canvas to verify paintEvent executes cleanly
        pix_wind = QPixmap(600, 450)
        dlg.wind_rose_widget.canvas.render(pix_wind)

        # 6. Retranslate UI
        self.cfg.set("app_language", "en")
        dlg.retranslate_ui()
        self.assertIn("Detailed Forecast", dlg.windowTitle())
        self.assertEqual(dlg.lbl_spline_title.text(), "Temperature Spline (24h)")
        self.assertEqual(dlg.lbl_baro_title.text(), "24h Barometric Trend")
        self.assertIn("1/3", dlg.lbl_screen_badge.text())
        dlg.close()
    def test_landmark_day_only_and_location_binding(self):
        # 1. Day theme: photo background is removed; seasonal or classic light theme used instead
        self.cfg.set("skin", {"theme_mode": "day"})
        self.cfg.set("seasonal_theme", {"enabled": True, "mode": "winter"})
        self.cfg.set("landmark", {
            "enabled": True,
            "image_path": "",
            "locations": {},
            "dimming": 0.35,
            "blur_radius": 3.0,
            "weather_effects": True,
            "active_effect": "auto",
        })
        window = WeatherWidgetWindowQt(provider=self.provider, config_manager=self.cfg)
        window._on_weather_updated_main_thread(self.data)

        # Must NOT be landmark-theme
        self.assertNotEqual(window.container.property("class"), "landmark-theme")
        self.assertEqual(window.container.property("class"), "light-theme")
        self.assertIsNotNone(window.container._seasonal_pixmap)

        # 2. Night theme with landmark enabled in config -> MUST BE DARK, NO SEASONAL, NO PHOTO
        self.cfg.set("skin", {"theme_mode": "night"})
        window._apply_theme()
        self.assertEqual(window.container.property("class"), "")
        self.assertIsNone(window.container._seasonal_pixmap)

        # 3. Settings dialog: 'Use photo as background' checkbox and photo controls are removed
        dlg = SettingsDialogQt(parent=None, config_manager=self.cfg)
        self.assertFalse(hasattr(dlg, "combo_landmark_loc"))
        self.assertFalse(hasattr(dlg, "lbl_landmark_preview"))
        # Ensure no 'Use photo as background' checkbox exists
        self.assertFalse(any(t("theme_landmark_enable") in cb.text() for cb in dlg.findChildren(QCheckBox)))
        # Weather effects selector is present in its dedicated group
        self.assertTrue(hasattr(dlg, "combo_effect"))
        self.assertEqual(dlg.combo_effect.count(), 2)
        # Check effect selection syncs active_effect and weather_effects
        dlg.combo_effect.setCurrentIndex(1)  # None
        self.assertEqual(self.cfg.get("landmark", {}).get("active_effect"), "none")
        self.assertFalse(self.cfg.get("landmark", {}).get("weather_effects"))
        dlg.combo_effect.setCurrentIndex(0)  # Auto
        self.assertEqual(self.cfg.get("landmark", {}).get("active_effect"), "auto")
        self.assertTrue(self.cfg.get("landmark", {}).get("weather_effects"))
        dlg.close()
        window.close()
    def test_settings_dialog_does_not_overlap_widget(self):
        window = WeatherWidgetWindowQt(provider=self.provider, config_manager=self.cfg)
        window.setGeometry(300, 200, 500, 150)
        window.show()
        window.open_settings_dialog()

        w_geom = window.frameGeometry()
        d_geom = window.settings_dialog.frameGeometry()
        self.assertFalse(d_geom.intersects(w_geom), "Settings dialog must not overlap widget")

        window.settings_dialog.close()
        window.close()

    def test_seasonal_daytime_themes(self):
        """Test seasonal day themes resolution, floating card background, and settings UI."""
        from core.seasonal import get_current_season, resolve_seasonal_theme_image

        cur_season = get_current_season()
        self.assertIn(cur_season, ("winter", "spring", "summer", "autumn"))

        for s in ("winter", "spring", "summer", "autumn"):
            img = resolve_seasonal_theme_image(s)
            self.assertIsNotNone(img, f"Seasonal image for {s} must be found")
            self.assertTrue(img.is_file(), f"File {img} must exist")

        auto_img = resolve_seasonal_theme_image("auto")
        self.assertIsNotNone(auto_img)
        self.assertTrue(auto_img.is_file())

        # Test application on WeatherWidgetWindowQt in day mode
        self.cfg.set("skin", {"theme_mode": "day"})
        self.cfg.set("landmark", {"enabled": False})
        self.cfg.set("seasonal_theme", {"enabled": True, "mode": "autumn"})
        window = WeatherWidgetWindowQt(provider=self.provider, config_manager=self.cfg)
        window._apply_theme()

        self.assertIsNotNone(window.container._seasonal_pixmap)
        self.assertFalse(window.container._seasonal_pixmap.isNull())
        # Safe inner margins
        margins = window.container_layout.contentsMargins()
        self.assertGreaterEqual(margins.left(), 30)
        self.assertGreaterEqual(margins.top(), 20)

        # Weather effects are clipped to the floating card artwork; otherwise
        # full-rect effects (sun rays/clouds/fog) paint a visible rectangle
        # over the transparent margins around the card.
        window.show()
        app.processEvents()
        mask = window.container.effects_layer.mask()
        self.assertFalse(mask.isEmpty())
        self.assertFalse(mask.contains(QtCore.QPoint(2, 2)))
        self.assertTrue(mask.contains(window.container.effects_layer.rect().center()))

        # Settings dialog seasonal UI check
        dlg = SettingsDialogQt(parent=None, config_manager=self.cfg)
        self.assertTrue(hasattr(dlg, "combo_seasonal_mode"))
        self.assertTrue(hasattr(dlg, "lbl_seasonal_preview"))
        self.assertEqual(dlg.combo_seasonal_mode.count(), 5)
        self.assertIsNotNone(dlg.lbl_seasonal_preview.pixmap())
        dlg.close()
        window.close()


if __name__ == "__main__":
    unittest.main()
