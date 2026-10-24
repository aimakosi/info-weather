"""PySide6 Astronomy (Восход / Закат / Луна) Block for info-weather."""

from __future__ import annotations

import math
from typing import Any

from core.astronomy import calculate_moon_phase, calculate_solar_details
from core.i18n import t
from models.weather import WeatherForecastData
from ui.qt_compat import (
    QColor,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QPixmap,
    QRectF,
    QSizePolicy,
    Qt,
    QTimer,
    QWidget,
)
from ui.utils import get_weather_icon_path


class AstronomyBlockWidget(QWidget):
    """Horizontal astronomical strip showing sunrise, sunset, day length, and moon phase."""

    def __init__(self, options: dict[str, Any] | None = None, scale: float = 1.0, parent: QWidget | None = None):
        super().__init__(parent)
        self.options = options or {"show_moon": True}
        self.scale = scale
        self.widget = self

        # Compact astronomy strip with clearly visible icons and text
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(max(16, int(18 * scale)))
        spacing = max(6, int(10 * scale))
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(spacing)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        lang = self.options.get("lang") or self.options.get("app_lang") or "ru"

        # 1. Sunrise
        self.sunrise_item = self._create_item("sunrise.svg", "07:00", t("weather_sunrise", _lang=lang))
        self.layout.addWidget(self.sunrise_item["container"])

        # 2. Sunset
        self.sunset_item = self._create_item("sunset.svg", "19:00", t("weather_sunset", _lang=lang))
        self.layout.addWidget(self.sunset_item["container"])

        # 3. Daylight duration
        self.duration_item = self._create_item("sun.svg", "12:00", t("weather_daylight", _lang=lang))
        self.layout.addWidget(self.duration_item["container"])

        # 4. Moon phase (rendered dynamically)
        self.moon_item = self._create_item("moon.svg", "—", t("weather_moon", _lang=lang))
        self.layout.addWidget(self.moon_item["container"])

        # 5. Geomagnetic activity (Kp index)
        self.geomagnetic_item = self._create_item("magnetic.svg", "—", t("weather_geomagnetic", _lang=lang))
        self.layout.addWidget(self.geomagnetic_item["container"])

    def _create_item(self, icon_file: str, placeholder: str, tooltip: str) -> dict[str, Any]:
        container = QWidget()
        container.setToolTip(tooltip)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(max(2, int(4 * self.scale)))
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_icon = QLabel()
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = get_weather_icon_path(icon_file)
        pix = QPixmap(icon_path)
        icon_size = max(12, int(14 * self.scale))
        if not pix.isNull():
            lbl_icon.setPixmap(
                pix.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

        lbl_val = QLabel(placeholder)
        lbl_val.setObjectName("AstroLabel")
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(lbl_icon)
        row.addWidget(lbl_val)

        return {
            "container": container,
            "icon_label": lbl_icon,
            "val_label": lbl_val,
            "icon_size": icon_size,
        }

    def _render_moon_phase(self, cycle_fraction: float, size: int) -> QPixmap:
        """Draw the current moon phase as a small anti-aliased pixmap."""
        ratio = 2
        canvas = max(12, size) * ratio
        pix = QPixmap(canvas, canvas)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = canvas * 0.10
        radius = (canvas - 2.0 * margin) / 2.0
        cx = cy = canvas / 2.0
        rect = QRectF(cx - radius, cy - radius, radius * 2.0, radius * 2.0)

        # Lit disk
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e2e8f0"))
        painter.drawEllipse(rect)

        # Shadow disk. Offset grows from 0 (new moon) to 2r (full moon).
        phase = cycle_fraction % 1.0
        illumination = 0.5 * (1.0 - math.cos(2.0 * math.pi * phase))
        offset = 2.0 * radius * illumination
        shadow_cx = cx - offset if phase <= 0.5 else cx + offset
        painter.setBrush(QColor(15, 23, 42, 215))
        painter.drawEllipse(
            QRectF(shadow_cx - radius, cy - radius, radius * 2.0, radius * 2.0)
        )

        # Outline keeps the disk visible at new moon
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#64748b"), max(1.0, canvas * 0.045)))
        painter.drawEllipse(rect)
        painter.end()

        pix.setDevicePixelRatio(ratio)
        return pix

    def update(self, data: WeatherForecastData) -> None:
        lat = data.lat or 55.75
        lon = data.lon or 37.61
        utc_offset_hours = (data.utc_offset_seconds or 0) / 3600.0
        weather_lang = self.options.get("lang") or self.options.get("app_lang") or "ru"

        solar = data.solar_details
        if solar and solar.sunrise not in ("00:00", "") and solar.sunset not in ("00:00", ""):
            sunrise = solar.sunrise
            sunset = solar.sunset
            dl_min = solar.daylight_min if solar.daylight_min > 0 else 720.0
        else:
            solar_dict = calculate_solar_details(
                lat=lat,
                lon=lon,
                utc_offset_hours=utc_offset_hours,
                lang=weather_lang,
            )
            sunrise = solar_dict.get("sunrise", "07:00")
            sunset = solar_dict.get("sunset", "19:00")
            dl_min = float(solar_dict.get("daylight_min", 720.0))

        h = int(dl_min // 60)
        m = int(round(dl_min % 60))
        daylight_duration = f"{h:02d}:{m:02d}"

        if weather_lang == "uk":
            daylight_str = f"{h} год {m} хв"
        elif weather_lang == "ru":
            daylight_str = f"{h} ч {m} мин"
        else:
            daylight_str = f"{h}h {m}m"

        self.sunrise_item["val_label"].setText(sunrise)
        self.sunrise_item["container"].setToolTip(f"{t('weather_sunrise', _lang=weather_lang)}: {sunrise}")

        self.sunset_item["val_label"].setText(sunset)
        self.sunset_item["container"].setToolTip(f"{t('weather_sunset', _lang=weather_lang)}: {sunset}")

        self.duration_item["val_label"].setText(daylight_duration)
        self.duration_item["container"].setToolTip(f"{t('weather_daylight', _lang=weather_lang)}: {daylight_str}")

        show_moon = bool(self.options.get("show_moon", True))
        self.moon_item["container"].setVisible(show_moon)
        if show_moon:
            moon = calculate_moon_phase(lang=weather_lang)
            illum = moon.get("illumination", 50)
            cycle_fraction = float(moon.get("cycle_fraction", 0.5))
            phase_name = moon.get("phase_name", "")

            self.moon_item["val_label"].setText(f"{illum}%")
            self.moon_item["icon_label"].setPixmap(
                self._render_moon_phase(cycle_fraction, self.moon_item["icon_size"])
            )
            self.moon_item["container"].setToolTip(f"{t('weather_moon', _lang=weather_lang)}: {phase_name} ({illum}%)")

        show_geomag = bool(self.options.get("show_geomagnetic", True))
        self.geomagnetic_item["container"].setVisible(show_geomag)
        if show_geomag:
            from core.geomagnetic import get_geomagnetic_activity

            def _on_async_geomag_ready(updated_geo: Any) -> None:
                try:
                    QTimer.singleShot(0, lambda: self._update_geomagnetic_ui(updated_geo, weather_lang))
                except Exception:
                    pass

            geo = get_geomagnetic_activity(on_updated=_on_async_geomag_ready)
            self._update_geomagnetic_ui(geo, weather_lang)

    def _update_geomagnetic_ui(self, geo: Any, weather_lang: str) -> None:
        kp_val = geo.kp_index
        level = geo.level
        status_desc = t(geo.status_key, _lang=weather_lang)

        if weather_lang == "uk":
            val_text = f"{round(kp_val)} б."
            tip_text = f"{t('weather_geomagnetic', _lang=weather_lang)}: {status_desc} ({round(kp_val)} б. з 9, Kp = {kp_val:.1f})"
        elif weather_lang == "ru":
            val_text = f"{round(kp_val)} б."
            tip_text = f"{t('weather_geomagnetic', _lang=weather_lang)}: {status_desc} ({round(kp_val)} б. из 9, Kp = {kp_val:.1f})"
        else:
            val_text = f"Kp {round(kp_val)}"
            tip_text = f"{t('weather_geomagnetic', _lang=weather_lang)}: {status_desc} (Kp = {kp_val:.1f} / 9)"

        if geo.noaa_scale and geo.noaa_scale != "G0":
            tip_text += f", {geo.noaa_scale}"

        self.geomagnetic_item["val_label"].setText(val_text)
        self.geomagnetic_item["container"].setToolTip(tip_text)

        if level >= 5:
            self.geomagnetic_item["val_label"].setStyleSheet(f"color: {geo.color}; font-weight: bold;")
        elif level >= 4:
            self.geomagnetic_item["val_label"].setStyleSheet(f"color: {geo.color};")
        else:
            self.geomagnetic_item["val_label"].setStyleSheet("")


AstronomyBlock = AstronomyBlockWidget
