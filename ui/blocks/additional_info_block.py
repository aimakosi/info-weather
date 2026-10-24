"""PySide6 Additional Info (Дополнительно) Block for info-weather.

Displays vertical list of meteorological indicators matching Gis-Weather:
- Wind with speed & direction
- Barometric pressure (мм рт. ст.)
- Relative humidity (%)
- Dew point / Precipitation probability
"""

from __future__ import annotations

from typing import Any

from core.i18n import t
from core.units import (
    cardinal_from_degrees,
    format_pressure,
    format_temp,
    format_wind_speed,
    mmhg_to_hpa,
)
from models.weather import WeatherForecastData
from ui.qt_compat import QHBoxLayout, QLabel, QPixmap, Qt, QVBoxLayout, QWidget
from ui.utils import get_weather_icon_path, is_light_theme_widget, render_colored_icon


class AdditionalInfoBlockWidget(QWidget):
    """Vertical compact list of additional meteorological indicators."""

    def __init__(self, options: dict[str, Any] | None = None, scale: float = 1.0, parent: QWidget | None = None):
        super().__init__(parent)
        self.options = options or {}
        self.scale = scale
        self.widget = self
        self._icons_light: bool | None = None

        spacing = max(2, int(4 * scale))
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(spacing)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 1. Wind row
        self.wind_row = self._create_row("wind.svg", "—")
        self.layout.addWidget(self.wind_row["container"])

        # 2. Pressure row
        self.press_row = self._create_row("gauge.svg", "—")
        self.layout.addWidget(self.press_row["container"])

        # 3. Humidity row
        self.hum_row = self._create_row("humidity.svg", "—")
        self.layout.addWidget(self.hum_row["container"])

        # 4. Dew point / Extra row
        self.extra_row = self._create_row("rain-drop.svg", "—")
        self.layout.addWidget(self.extra_row["container"])

    def _create_row(self, icon_file: str, placeholder: str) -> dict[str, Any]:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(max(3, int(6 * self.scale)))
        row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        lbl_icon = QLabel()
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = get_weather_icon_path(icon_file)
        pix = QPixmap(icon_path)
        icon_size = max(12, int(16 * self.scale))
        if not pix.isNull():
            lbl_icon.setPixmap(
                pix.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

        lbl_val = QLabel(placeholder)
        lbl_val.setObjectName("MetricValue")
        lbl_val.setStyleSheet("font-size: 11px; font-weight: 500;")
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(lbl_icon)
        row.addWidget(lbl_val)

        return {
            "container": container,
            "icon_label": lbl_icon,
            "val_label": lbl_val,
            "icon_name": icon_file,
            "icon_size": icon_size,
        }

    def _refresh_icons(self) -> None:
        """Tint the service icons for the current light/dark background."""
        light = is_light_theme_widget(self)
        if self._icons_light == light:
            return
        self._icons_light = light
        color = "#334155" if light else "#cbd5e1"
        for row in (self.wind_row, self.press_row, self.hum_row, self.extra_row):
            self._set_row_icon(row, color)

    def _set_row_icon(self, row: dict[str, Any], color: str) -> None:
        name = row.get("icon_name")
        if not name:
            return
        row["icon_label"].setPixmap(
            render_colored_icon(name, row.get("icon_size", 16), color)
        )

    def update(self, data: WeatherForecastData) -> None:
        self._refresh_icons()
        cur = data.current
        weather_lang = self.options.get("lang") or "ru"

        # 1. Wind
        w_speed = format_wind_speed(
            cur.wind_speed,
            self.options.get("wind_unit", "m_s"),
            lang=weather_lang,
        )
        cardinal = cardinal_from_degrees(cur.wind_direction, lang=weather_lang) or cur.wind_cardinal or ""
        self.wind_row["val_label"].setText(f"{w_speed} {cardinal}".strip())
        self.wind_row["container"].setToolTip(f"{t('weather_wind', _lang=weather_lang)}: {w_speed} {cardinal}".strip())

        # 2. Pressure (respects the pressure unit selected in Settings → Units)
        pressure_hpa = cur.pressure_hpa
        if pressure_hpa is None and cur.pressure_mm is not None:
            pressure_hpa = mmhg_to_hpa(cur.pressure_mm)
        p_str = format_pressure(
            pressure_hpa,
            self.options.get("pressure_unit", "mmHg"),
            lang=weather_lang,
        )
        self.press_row["val_label"].setText(p_str)
        self.press_row["container"].setToolTip(f"{t('weather_pressure', _lang=weather_lang)}: {p_str}")

        # 3. Humidity
        self.hum_row["val_label"].setText(
            f"{cur.humidity}% {t('weather_humidity_short', _lang=weather_lang)}"
        )
        self.hum_row["container"].setToolTip(
            f"{t('weather_humidity', _lang=weather_lang)}: {cur.humidity}%"
        )

        # 4. Dew point or precipitation probability
        if cur.dew_point is not None:
            dew_point = format_temp(
                cur.dew_point,
                self.options.get("temp_unit", "celsius"),
            )
            txt = f"{t('weather_dew_point', _lang=weather_lang)}: {dew_point}"
            self.extra_row["val_label"].setText(txt)
            self.extra_row["container"].setToolTip(txt)
            self.extra_row["container"].setVisible(True)
        elif data.daily and data.daily[0].precip_prob_max:
            txt = f"{t('weather_precipitation', _lang=weather_lang)}: {data.daily[0].precip_prob_max}%"
            self.extra_row["val_label"].setText(txt)
            self.extra_row["container"].setToolTip(txt)
            self.extra_row["container"].setVisible(True)
        else:
            self.extra_row["container"].setVisible(False)


AdditionalInfoBlock = AdditionalInfoBlockWidget
MetricsBlock = AdditionalInfoBlockWidget
