"""PySide6 Multi-day forecast block matching Gis-Weather reference."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.i18n import format_date_str, get_weekday_name
from core.units import format_temp
from data.wmo_conditions import WMO_INFO, get_condition_text
from models.weather import WeatherForecastData
from ui.qt_compat import (
    QFont,
    QHBoxLayout,
    QLabel,
    QPixmap,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)
from ui.utils import get_weather_icon_path, is_weekend_day


class DailyBlockWidget(QWidget):
    """Horizontal daily forecast strip matching Gis-Weather reference layout."""

    def __init__(self, options: dict[str, Any] | None = None, scale: float = 1.0, parent: QWidget | None = None):
        super().__init__(parent)
        self.options = options or {"days": 5, "horizontal": True}
        self.scale = scale
        self.horizontal = True
        self.rows: list[dict[str, Any]] = []
        self.widget = self

        spacing = max(2, int(4 * scale))
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(spacing)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        max_days = int(self.options.get("days", 5))
        for _ in range(max_days):
            col = self._create_column()
            self.main_layout.addWidget(col["container"])
            self.rows.append(col)

    def _create_column(self) -> dict[str, Any]:
        """Create a single daily column: Day/Date -> Temp + Icon side-by-side -> Condition text."""
        container = QWidget()
        container.setProperty("class", "daily-col")
        col_width = max(78, int(84 * self.scale))
        container.setFixedWidth(col_width)
        container.setMinimumHeight(max(64, int(76 * self.scale)))
        container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        col_layout = QVBoxLayout(container)
        col_layout.setContentsMargins(2, 1, 2, 1)
        col_layout.setSpacing(max(1, int(1 * self.scale)))

        # 1. Day & Date label (left-aligned)
        day_lbl = QLabel("—")
        day_lbl.setObjectName("DailyDay")
        day_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        col_layout.addWidget(day_lbl)

        # 2. Middle Row: Left = Temp stack (Max / Min), Right = Weather Icon
        icon_size = max(30, int(38 * self.scale))
        mid_widget = QWidget()
        mid_widget.setFixedHeight(icon_size)
        mid_row = QHBoxLayout(mid_widget)
        mid_row.setContentsMargins(0, 0, 0, 0)
        mid_row.setSpacing(max(2, int(3 * self.scale)))
        mid_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        temp_box = QWidget()
        temp_layout = QVBoxLayout(temp_box)
        temp_layout.setContentsMargins(0, 0, 0, 0)
        temp_layout.setSpacing(0)
        temp_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        max_lbl = QLabel("--°")
        max_lbl.setObjectName("DailyTempMax")
        max_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        min_lbl = QLabel("--°")
        min_lbl.setObjectName("DailyTempMin")
        min_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        temp_layout.addWidget(max_lbl)
        temp_layout.addWidget(min_lbl)
        mid_row.addWidget(temp_box)

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setFixedSize(icon_size, icon_size)
        mid_row.addWidget(img_lbl)

        col_layout.addWidget(mid_widget)

        # 3. Short condition text (left-aligned, wrapped, compact)
        cond_lbl = QLabel("")
        cond_lbl.setObjectName("DailyCondition")
        cond_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        cond_lbl.setWordWrap(True)
        # Fixed text width keeps wrapping by words consistent for every day,
        # regardless of the length of the condition description.
        cond_lbl.setFixedWidth(max(40, col_width - 4))
        cond_lbl.setMinimumHeight(max(16, int(22 * self.scale)))
        cond_lbl.setMaximumHeight(max(26, int(30 * self.scale)))
        col_layout.addWidget(cond_lbl)
        col_layout.addStretch(1)

        # Apply small font if specified in options
        small_family = self.options.get("small_font_family")
        small_size = self.options.get("small_font_size", 9)
        if small_family:
            for lbl in (day_lbl, cond_lbl, min_lbl, max_lbl):
                lbl.setProperty("smallFont", True)
            try:
                base_f = QFont(small_family, int(small_size))
                day_f = QFont(small_family, int(small_size) + 1, QFont.Weight.Bold)
                day_lbl.setFont(day_f)
                cond_lbl.setFont(QFont(small_family, max(8, int(small_size))))
                min_lbl.setFont(base_f)
                max_f = QFont(small_family, int(small_size) + 3, QFont.Weight.Bold)
                max_lbl.setFont(max_f)
            except Exception:
                pass

        return {
            "container": container,
            "day_label": day_lbl,
            "image": img_lbl,
            "cond_label": cond_lbl,
            "min_label": min_lbl,
            "max_label": max_lbl,
        }

    def update(self, data: WeatherForecastData) -> None:
        """Update daily columns with weather forecast data."""
        days_count = int(self.options.get("days", 5))
        daily_list = data.daily[1:days_count + 1] if len(data.daily) > 1 else data.daily

        for idx, row in enumerate(self.rows):
            if idx < len(daily_list):
                d = daily_list[idx]
                row["container"].setVisible(True)

                weather_lang = self.options.get("lang") or "ru"

                # Day label (e.g. "Пт, 16.10" or "Fri, 16.10")
                w_idx = d.weekday_idx
                if d.date_str and len(d.date_str) >= 10:
                    try:
                        w_idx = datetime.strptime(d.date_str[:10], "%Y-%m-%d").weekday()
                    except Exception:
                        pass
                day_title = get_weekday_name(w_idx, short=True, lang=weather_lang) if w_idx is not None else d.day
                date_part = format_date_str(
                    d.date_str,
                    str(self.options.get("date_format", "DD.MM")),
                    lang=weather_lang,
                )
                date_suffix = f", {date_part}" if date_part else ""
                row["day_label"].setText(f"{day_title}{date_suffix}")

                # Weekend color highlight
                weekend_def = self.options.get("weekend", "Sa, Su")
                weekend_clr = self.options.get("weekend_color", "#ef4444")
                if w_idx is not None and is_weekend_day(w_idx, weekend_def):
                    row["day_label"].setStyleSheet(f"color: {weekend_clr}; font-weight: bold;")
                else:
                    row["day_label"].setStyleSheet("font-weight: bold;")

                # Weather Icon
                wmo_entry = WMO_INFO.get(d.code, {})
                icon_name = d.icon_name
                if not icon_name or icon_name in ("clear-day", "clear-night"):
                    icon_name = wmo_entry.get("icon_day", icon_name or "clear-day.svg")

                icon_path = get_weather_icon_path(icon_name or d.code, is_day=1, code=d.code)
                pix = QPixmap(icon_path)
                icon_size = max(34, int(42 * self.scale))
                if not pix.isNull():
                    row["image"].setPixmap(pix.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

                # Temperatures (Max & Min)
                row["max_label"].setText(format_temp(d.max, self.options.get("temp_unit", "celsius")))
                row["min_label"].setText(format_temp(d.min, self.options.get("temp_unit", "celsius")))

                # Short condition text
                cond_text = get_condition_text(d.code, lang=weather_lang)
                show_precip = self.options.get("show_precip_prob", False)
                if show_precip and d.precip_prob_max and d.precip_prob_max >= 20:
                    display_text = f"{cond_text} ({d.precip_prob_max}%)"
                else:
                    display_text = cond_text
                row["cond_label"].setText(display_text)

                row["container"].setToolTip(f"{day_title}{date_suffix}: {cond_text}, {format_temp(d.min, self.options.get('temp_unit', 'celsius'))}…{format_temp(d.max, self.options.get('temp_unit', 'celsius'))}")
            else:
                row["container"].setVisible(False)


DailyBlock = DailyBlockWidget
HourlyBlock = DailyBlockWidget
