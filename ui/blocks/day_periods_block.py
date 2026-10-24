"""PySide6 Day periods (Времена суток) block matching Gis-Weather."""

from __future__ import annotations

from typing import Any

from core.units import cardinal_from_degrees, format_temp
from models.weather import WeatherForecastData
from ui.qt_compat import QFont, QGridLayout, QHBoxLayout, QLabel, QPixmap, Qt, QVBoxLayout, QWidget
from ui.utils import get_weather_icon_path


class DayPeriodsBlockWidget(QWidget):
    """Outlook for 4 periods of the day: Night, Morning, Day, Evening."""

    def __init__(self, options: dict[str, Any] | None = None, scale: float = 1.0, parent: QWidget | None = None):
        super().__init__(parent)
        self.options = options or {}
        self.scale = scale
        self.mode = self.options.get("mode", "tomorrow")
        self.header_title = self.options.get("title", "Завтра" if self.mode == "tomorrow" else "Сегодня")
        self.widget = self

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(max(1, int(3 * scale)))
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Header Title
        self.lbl_title = QLabel(self.header_title)
        self.lbl_title.setObjectName("PeriodHeader")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_title)

        # 2x2 Grid
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(max(4, int(10 * scale)))
        grid.setVerticalSpacing(max(2, int(4 * scale)))

        self.period_cells: dict[str, dict[str, Any]] = {}
        weather_lang = self.options.get("lang") or "ru"
        period_map = {
            "uk": {"night": "Ніч", "morning": "Ранок", "day": "День", "evening": "Вечір"},
            "en": {"night": "Night", "morning": "Morning", "day": "Day", "evening": "Evening"},
            "ru": {"night": "Ночь", "morning": "Утро", "day": "День", "evening": "Вечер"},
        }.get(weather_lang, {"night": "Ночь", "morning": "Утро", "day": "День", "evening": "Вечер"})

        periods_def = [
            ("night", period_map["night"], 0, 0),
            ("morning", period_map["morning"], 0, 1),
            ("day", period_map["day"], 1, 0),
            ("evening", period_map["evening"], 1, 1),
        ]

        for p_id, p_label, row, col in periods_def:
            cell = self._create_period_cell(p_label)
            grid.addWidget(cell["container"], row, col)
            self.period_cells[p_id] = cell

        main_layout.addWidget(grid_widget)
        self._apply_font_options()

    def _apply_font_options(self) -> None:
        """Use the small (forecast) font for the tomorrow outlook."""
        family = self.options.get("small_font_family")
        if not family or self.mode != "tomorrow":
            return
        try:
            size = int(self.options.get("small_font_size", 9))
        except (TypeError, ValueError):
            size = 9
        font = QFont(str(family), size)
        self.lbl_title.setProperty("smallFont", True)
        self.lbl_title.setFont(font)
        for cell in self.period_cells.values():
            for key in ("name_label", "temp_label", "wind_label"):
                if key in cell:
                    cell[key].setProperty("smallFont", True)
                    cell[key].setFont(font)

    def _create_period_cell(self, title: str) -> dict[str, Any]:
        container = QWidget()
        container.setProperty("class", "period-cell")
        box = QVBoxLayout(container)
        box.setContentsMargins(2, 1, 2, 1)
        box.setSpacing(1)

        # Top line: Title (e.g. "Ночь") + Temp (e.g. "-10°")
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(max(2, int(4 * self.scale)))

        lbl_name = QLabel(title)
        lbl_name.setObjectName("PeriodTitle")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        lbl_temp = QLabel("--°")
        lbl_temp.setObjectName("PeriodTemp")
        lbl_temp.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top_row.addWidget(lbl_name)
        top_row.addWidget(lbl_temp)
        box.addLayout(top_row)

        # Middle line: Icon + Wind
        mid_row = QHBoxLayout()
        mid_row.setContentsMargins(0, 0, 0, 0)
        mid_row.setSpacing(max(2, int(4 * self.scale)))

        lbl_img = QLabel()
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        lbl_wind = QLabel("")
        lbl_wind.setObjectName("PeriodWind")
        lbl_wind.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        mid_row.addWidget(lbl_img)
        mid_row.addWidget(lbl_wind)
        box.addLayout(mid_row)

        return {
            "container": container,
            "name_label": lbl_name,
            "temp_label": lbl_temp,
            "img_label": lbl_img,
            "wind_label": lbl_wind,
        }

    def update(self, data: WeatherForecastData) -> None:
        target_day_idx = 1 if self.mode == "tomorrow" else 0
        periods_data = self._extract_periods(data, target_day_idx)

        icon_size = max(16, int(22 * self.scale))
        for p_id, cell in self.period_cells.items():
            info = periods_data.get(p_id, {})
            temp_val = info.get("temp")
            if temp_val is not None:
                cell["temp_label"].setText(format_temp(temp_val, self.options.get("temp_unit", "celsius")))
            else:
                cell["temp_label"].setText("--°")

            icon_name = info.get("icon_name", "weather-clouds")
            is_day = info.get("is_day", 1)
            code = info.get("code")
            icon_path = get_weather_icon_path(icon_name, is_day=is_day, code=code)
            pix = QPixmap(icon_path)
            if not pix.isNull():
                cell["img_label"].setPixmap(
                    pix.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )

            w_speed = info.get("wind_speed", 0.0)
            w_dir = info.get("wind_cardinal", "")
            weather_lang = self.options.get("lang") or "ru"
            unit_wind = "м/с" if weather_lang in ("ru", "uk") else "m/s"
            if w_speed > 0:
                cell["wind_label"].setText(f"{w_dir} {round(w_speed)} {unit_wind}".strip())
            else:
                cell["wind_label"].setText("")

            # Localized tooltip
            p_title = cell["name_label"].text()
            t_str = format_temp(temp_val, self.options.get("temp_unit", "celsius")) if temp_val is not None else "--°"
            wind_str = f", {w_dir} {round(w_speed)} {unit_wind}".strip() if w_speed > 0 else ""
            cell["container"].setToolTip(f"{p_title}: {t_str}{wind_str}")

    def _extract_periods(self, data: WeatherForecastData, day_idx: int) -> dict[str, dict[str, Any]]:
        res: dict[str, dict[str, Any]] = {}
        target_hours = {
            "night": 3,
            "morning": 9,
            "day": 15,
            "evening": 21,
        }

        # Strategy 1: from days_detailed if available
        if data.days_detailed and len(data.days_detailed) > day_idx:
            day_det = data.days_detailed[day_idx]
            for p_id, h in target_hours.items():
                if len(day_det.hourly_temps) > h:
                    temp = day_det.hourly_temps[h]
                    code = day_det.hourly_codes[h] if len(day_det.hourly_codes) > h else 0
                    is_day = (
                        day_det.hourly_is_days[h]
                        if len(day_det.hourly_is_days) > h
                        else (0 if p_id in ("night", "evening") else 1)
                    )
                    w_spd = day_det.hourly_winds[h] if len(day_det.hourly_winds) > h else 0.0
                    w_deg = day_det.hourly_wind_dirs[h] if len(day_det.hourly_wind_dirs) > h else 0
                    weather_lang = self.options.get("lang") or "ru"
                    w_card = cardinal_from_degrees(w_deg, lang=weather_lang)
                    res[p_id] = {
                        "temp": temp,
                        "code": code,
                        "icon_name": f"code_{code}",
                        "is_day": is_day,
                        "wind_speed": w_spd,
                        "wind_cardinal": w_card,
                    }
            if len(res) == 4:
                return res

        # Strategy 2: from data.hourly (flat list)
        offset = day_idx * 24
        if data.hourly and len(data.hourly) >= offset + 24:
            weather_lang = self.options.get("lang") or "ru"
            for p_id, h in target_hours.items():
                h_item = data.hourly[offset + h]
                res[p_id] = {
                    "temp": h_item.temp,
                    "code": h_item.code,
                    "icon_name": h_item.icon_name or f"code_{h_item.code}",
                    "is_day": h_item.is_day,
                    "wind_speed": h_item.wind_speed,
                    "wind_cardinal": cardinal_from_degrees(h_item.wind_direction, lang=weather_lang),
                }
            if len(res) == 4:
                return res

        # Strategy 3: fallback estimation from daily summary
        if data.daily and len(data.daily) > day_idx:
            d = data.daily[day_idx]
            res = {
                "night": {"temp": d.min, "icon_name": d.icon_name, "code": d.code, "is_day": 0, "wind_speed": 2.0, "wind_cardinal": "W"},
                "morning": {"temp": round((d.min + d.max) / 2), "icon_name": d.icon_name, "code": d.code, "is_day": 1, "wind_speed": 2.5, "wind_cardinal": "W"},
                "day": {"temp": d.max, "icon_name": d.icon_name, "code": d.code, "is_day": 1, "wind_speed": 3.0, "wind_cardinal": "SW"},
                "evening": {"temp": round((d.min + d.max) / 2), "icon_name": d.icon_name, "code": d.code, "is_day": 0, "wind_speed": 2.0, "wind_cardinal": "W"},
            }
        return res


DayPeriodsBlock = DayPeriodsBlockWidget


class TodayBlock(DayPeriodsBlockWidget):
    """Compatibility alias for today period block."""
    def __init__(self, options: dict[str, Any] | None = None, scale: float = 1.0, parent: QWidget | None = None):
        opts = dict(options or {})
        opts.setdefault("mode", "today")
        opts.setdefault("title", "Сегодня")
        super().__init__(options=opts, scale=scale, parent=parent)
