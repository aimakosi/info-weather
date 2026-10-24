"""PySide6 Header / Now Weather Block matching Gis-Weather center display."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.i18n import format_date_str, get_weekday_name, t
from core.units import format_temp
from data.wmo_conditions import get_condition_text
from models.weather import WeatherForecastData
from ui.qt_compat import QHBoxLayout, QLabel, QPixmap, Qt, QVBoxLayout, QWidget
from ui.utils import get_weather_icon_path


class HeaderBlockWidget(QWidget):
    """Now weather block: date, city, current temperature, large icon, and condition."""

    def __init__(self, options: dict[str, Any] | None = None, scale: float = 1.0, parent: QWidget | None = None):
        super().__init__(parent)
        self.options = options or {}
        self.scale = scale
        self.widget = self  # Compatibility with block wrapper access

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, max(2, int(4 * scale)), 0, 0)
        self.layout.setSpacing(max(1, int(1 * scale)))
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Date (e.g. "Thu, 15.10")
        self.lbl_date = QLabel("—")
        self.lbl_date.setObjectName("HeaderDate")
        self.lbl_date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_date)

        # 2. City name (e.g. "Abakan")
        self.lbl_city = QLabel("—")
        self.lbl_city.setObjectName("HeaderCity")
        self.lbl_city.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_city)

        # 3. Temp + Icon row
        temp_icon_row = QHBoxLayout()
        temp_icon_row.setContentsMargins(0, 0, 0, 0)
        temp_icon_row.setSpacing(max(4, int(8 * scale)))
        temp_icon_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_temp = QLabel("--°")
        self.lbl_temp.setObjectName("HeaderTemp")
        self.lbl_temp.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        temp_icon_row.addWidget(self.lbl_temp)

        icon_size = max(44, int(64 * scale))
        self.lbl_icon = QLabel()
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_icon.setFixedSize(icon_size, icon_size)
        temp_icon_row.addWidget(self.lbl_icon)

        self.layout.addLayout(temp_icon_row)

        # 4. Condition text
        self.lbl_cond = QLabel("—")
        self.lbl_cond.setObjectName("HeaderCondition")
        self.lbl_cond.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cond.setWordWrap(True)
        self.layout.addWidget(self.lbl_cond)

    def update(self, data: WeatherForecastData) -> None:
        """Update view with meteorological data."""
        cur = data.current
        weather_lang = self.options.get("lang") or "ru"

        from data.resources import localize_city
        loc_city, _ = localize_city(
            name=data.city_name,
            lat=data.lat,
            lon=data.lon,
            country=data.country,
            lang=weather_lang,
        )
        self.lbl_city.setText(loc_city or data.city_name or "—")

        # Date string from solar or today
        if data.daily and data.daily[0].date_str:
            d0 = data.daily[0]
            date_part = format_date_str(
                d0.date_str,
                str(self.options.get("date_format", "DD.MM")),
                lang=weather_lang,
            )
            if not date_part:
                date_part = d0.date_str[5:].replace("-", ".")
            w_idx = d0.weekday_idx
            if len(d0.date_str) >= 10:
                try:
                    w_idx = datetime.strptime(d0.date_str[:10], "%Y-%m-%d").weekday()
                except Exception:
                    pass
            w_name = get_weekday_name(w_idx, short=True, lang=weather_lang) if w_idx is not None else d0.day
            self.lbl_date.setText(f"{w_name}, {date_part}")
        else:
            self.lbl_date.setText(t("weather_today", _lang=weather_lang))

        # Temperature
        self.lbl_temp.setText(format_temp(cur.temp, self.options.get("temp_unit", "celsius")))

        # Icon
        icon_path = get_weather_icon_path(cur.icon_name or cur.weather_code, is_day=cur.is_day, code=cur.weather_code)
        pix = QPixmap(icon_path)
        icon_size = max(44, int(64 * self.scale))
        self.lbl_icon.setFixedSize(icon_size, icon_size)
        if not pix.isNull():
            self.lbl_icon.setPixmap(pix.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        # Condition
        if cur.condition_text and "lang" not in self.options:
            cond_text = cur.condition_text
        elif cur.weather_code is not None:
            cond_text = get_condition_text(cur.weather_code, lang=weather_lang, is_day=bool(cur.is_day))
        else:
            cond_text = cur.condition_text or ""
        self.lbl_cond.setText(cond_text)

        # Tooltips synchronized with language setting
        feels_val = format_temp(cur.feels_like, self.options.get("temp_unit", "celsius"))
        feels_tip = f"{t('weather_feels_like', _lang=weather_lang)}: {feels_val}"
        self.lbl_temp.setToolTip(feels_tip)
        self.lbl_icon.setToolTip(f"{cond_text} ({feels_tip})" if cond_text else feels_tip)
        self.lbl_cond.setToolTip(cond_text)


HeaderBlock = HeaderBlockWidget
