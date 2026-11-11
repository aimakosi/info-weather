"""Detailed Forecast Dialog in PySide6 / Qt6 for info-weather.

Features 2 focused analytical screens:
1. 24h Hourly Temperature Spline & Barometric Trend / Tendency
2. ERA5 30-Year Climate Normals Comparison & 12-Month Annual Profile
with a modern segmented pill switcher.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.i18n import get_month_name, get_weekday_name, set_language, t
from core.units import (
    cardinal_from_degrees,
    convert_pressure,
    format_pressure,
    format_temp,
    format_wind_speed,
)
from data.resources import get_era5_baseline
from data.wmo_conditions import get_condition_text
from models.weather import WeatherForecastData
from ui.dialogs.wind_rose_widget import FullWindRoseWidget
from ui.qt_compat import (
    QColor,
    QDialog,
    QFont,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPushButton,
    QRectF,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    Qt,
    QtCore,
    QVBoxLayout,
    QWidget,
)
from ui.utils import get_weather_icon_path, is_system_light_theme, render_colored_icon


class SegmentedPillToggle(QFrame):
    """Modern rounded pill toggle switcher for detailed forecast screens."""

    def __init__(self, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels = labels
        self._current_index = 0
        self._buttons: list[QPushButton] = []
        self._is_light = False

        self.setObjectName("SegmentedPillToggle")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(44)
        self.setFixedWidth(540)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        for idx, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _, i=idx: self.set_index(i, notify=True))
            layout.addWidget(btn)
            self._buttons.append(btn)

        self._update_styles()

    def sizeHint(self) -> QtCore.QSize:
        w = sum(btn.sizeHint().width() for btn in self._buttons) + len(self._buttons) * 16 + 24
        return QtCore.QSize(max(440, w), 44)

    def set_index(self, index: int, notify: bool = True) -> None:
        if 0 <= index < len(self._buttons) and index != self._current_index:
            self._current_index = index
            self._update_styles()
            if notify:
                parent = self.parent()
                if hasattr(parent, "_on_tab_switched"):
                    parent._on_tab_switched(index)

    def current_index(self) -> int:
        return self._current_index

    def update_labels(self, labels: list[str]) -> None:
        self._labels = labels
        for btn, label in zip(self._buttons, labels):
            btn.setText(label)
        self.adjustSize()

    def set_theme_light(self, is_light: bool) -> None:
        self._is_light = is_light
        self._update_styles()

    def _update_styles(self) -> None:
        bg_bar = "#1e293b" if not self._is_light else "#e2e8f0"
        border_bar = "#334155" if not self._is_light else "#cbd5e1"
        inactive_color = "#94a3b8" if not self._is_light else "#475569"
        inactive_hover_bg = "rgba(255, 255, 255, 0.08)" if not self._is_light else "rgba(0, 0, 0, 0.06)"
        inactive_hover_col = "#ffffff" if not self._is_light else "#0f172a"

        self.setStyleSheet(f"""
            QFrame#SegmentedPillToggle {{
                background-color: {bg_bar};
                border: 1.5px solid {border_bar};
                border-radius: 22px;
            }}
            QPushButton#PillBtnActive {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0284c7, stop:1 #38bdf8);
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 17px;
                padding: 4px 22px;
            }}
            QPushButton#PillBtnInactive {{
                background: transparent;
                color: {inactive_color};
                font-weight: 600;
                font-size: 13px;
                border: none;
                border-radius: 17px;
                padding: 4px 22px;
            }}
            QPushButton#PillBtnInactive:hover {{
                color: {inactive_hover_col};
                background-color: {inactive_hover_bg};
            }}
        """)

        for idx, btn in enumerate(self._buttons):
            if idx == self._current_index:
                btn.setObjectName("PillBtnActive")
            else:
                btn.setObjectName("PillBtnInactive")
            btn.style().unpolish(btn)
            btn.style().polish(btn)


class HourlySplineChartWidget(QWidget):
    """Temperature smooth Bezier spline supporting 24h hourly and multi-day day/night curves."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(240)
        # Expanding vertically: fills the pane's static height instead of
        # leaving the extra space to the title label above.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        self._mode = "hourly"  # "hourly" or "daily"
        self._points: list[dict[str, Any]] = []
        self._daily_points: list[dict[str, Any]] = []
        self._temp_unit = "C"
        self._wind_unit = "m/s"
        self._lang = "ru"
        self._is_light = False
        self._hover_idx: int | None = None

    def set_theme_light(self, is_light: bool) -> None:
        self._is_light = is_light
        self.update()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._hover_idx = None
        self.update()

    def update_points(
        self,
        points: list[dict[str, Any]],
        temp_unit: str = "C",
        wind_unit: str = "m/s",
        lang: str = "ru",
        is_light: bool = False,
    ) -> None:
        self._mode = "hourly"
        self._points = points
        self._temp_unit = temp_unit
        self._wind_unit = wind_unit
        self._lang = lang
        self._is_light = is_light
        self._hover_idx = None
        self.update()

    def update_daily_points(
        self,
        daily_points: list[dict[str, Any]],
        temp_unit: str = "C",
        wind_unit: str = "m/s",
        lang: str = "ru",
        is_light: bool = False,
    ) -> None:
        self._mode = "daily"
        self._daily_points = daily_points
        self._temp_unit = temp_unit
        self._wind_unit = wind_unit
        self._lang = lang
        self._is_light = is_light
        self._hover_idx = None
        self.update()

    @staticmethod
    def _day_night_labels(lang: str = "ru") -> tuple[str, str]:
        """Localized Day / Night labels for the scrub tooltip of the daily chart."""
        return t("forecast_legend_day", _lang=lang), t("forecast_legend_night", _lang=lang)

    @staticmethod
    def _build_spline_path(coords: list[tuple[float, float]]) -> QPainterPath:
        path = QPainterPath()
        if not coords:
            return path
        path.moveTo(coords[0][0], coords[0][1])
        if len(coords) == 1:
            return path
        for i in range(len(coords) - 1):
            p0 = coords[max(0, i - 1)]
            p1 = coords[i]
            p2 = coords[i + 1]
            p3 = coords[min(len(coords) - 1, i + 2)]

            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
        return path

    def mouseMoveEvent(self, event: Any) -> None:
        pts = self._daily_points if self._mode == "daily" else self._points
        if not pts:
            return
        w = self.width()
        pad_l = 44.0 if self._mode == "daily" else 36.0
        pad_r = 44.0 if self._mode == "daily" else 36.0
        plot_w = max(10.0, w - pad_l - pad_r)

        x = event.position().x() if hasattr(event, "position") else event.x()
        if pad_l <= x <= w - pad_r:
            step = plot_w / max(1, len(pts) - 1)
            idx = int(round((x - pad_l) / step))
            idx = max(0, min(len(pts) - 1, idx))
            if idx != self._hover_idx:
                self._hover_idx = idx
                self.update()
        else:
            if self._hover_idx is not None:
                self._hover_idx = None
                self.update()

    def leaveEvent(self, event: Any) -> None:
        if self._hover_idx is not None:
            self._hover_idx = None
            self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w = self.width()
        h = self.height()

        if self._mode == "daily":
            self._paint_daily(painter, w, h)
        else:
            self._paint_hourly(painter, w, h)

    def _paint_hourly(self, painter: QPainter, w: int, h: int) -> None:
        if len(self._points) < 2:
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("weather_no_data"))
            return

        pad_l = 36.0
        pad_r = 36.0
        pad_t = 54.0   # Space for top weather icon and temperature text
        pad_b = 56.0   # Space for wind speed and rotated arrow
        plot_w = max(10.0, w - pad_l - pad_r)
        plot_h = max(10.0, h - pad_t - pad_b)

        temps = [float(p.get("temp", 0.0)) for p in self._points]
        min_t = min(temps)
        max_t = max(temps)
        if max_t - min_t < 4.0:
            max_t += 2.0
            min_t -= 2.0

        n = len(self._points)
        step_x = plot_w / max(1, n - 1)

        coords: list[tuple[float, float]] = []
        for i, t_val in enumerate(temps):
            cx = pad_l + i * step_x
            cy = pad_t + plot_h - ((t_val - min_t) / (max_t - min_t)) * plot_h
            coords.append((cx, cy))

        # 1. Subtle horizontal temperature grid lines
        grid_pen = QPen(QColor(0, 0, 0, 15) if self._is_light else QColor(255, 255, 255, 15), 1.0)
        painter.setPen(grid_pen)
        for g_frac in (0.0, 0.5, 1.0):
            gy = pad_t + g_frac * plot_h
            painter.drawLine(int(pad_l), int(gy), int(w - pad_r), int(gy))

        # 2. Smooth cubic Bezier spline
        path = self._build_spline_path(coords)

        # Fill under curve
        fill_path = QPainterPath(path)
        fill_path.lineTo(coords[-1][0], pad_t + plot_h + 10)
        fill_path.lineTo(coords[0][0], pad_t + plot_h + 10)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, pad_t, 0, pad_t + plot_h + 10)
        if self._is_light:
            grad.setColorAt(0.0, QColor(2, 132, 199, 85))
            grad.setColorAt(1.0, QColor(2, 132, 199, 5))
            curve_color = QColor(2, 132, 199)
        else:
            grad.setColorAt(0.0, QColor(56, 189, 248, 90))
            grad.setColorAt(1.0, QColor(56, 189, 248, 5))
            curve_color = QColor(56, 189, 248)

        painter.fillPath(fill_path, grad)

        # Draw stroke
        curve_pen = QPen(curve_color, 2.8)
        curve_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        curve_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(curve_pen)
        painter.drawPath(path)

        # 3. Draw points, icons, temp labels and wind indicators
        step_display = 1 if n <= 12 else (2 if n <= 18 else 3)
        font_temp = QFont("Sans Serif", 9)
        font_temp.setBold(True)
        font_time = QFont("Sans Serif", 8)
        font_wind = QFont("Sans Serif", 8)

        for i, (cx, cy) in enumerate(coords):
            p = self._points[i]
            is_hover = (i == self._hover_idx)
            is_draw_point = (i % step_display == 0) or (i == n - 1) or is_hover

            # Dot on curve
            dot_r = 4.5 if is_hover else 2.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255) if not is_hover else QColor(251, 146, 60))
            painter.drawEllipse(int(cx - dot_r), int(cy - dot_r), int(dot_r * 2), int(dot_r * 2))

            if not is_draw_point and not is_hover:
                continue

            # Weather Icon
            code = p.get("code", 0)
            is_day = p.get("is_day", 1)
            icon_path = get_weather_icon_path(code, is_day=is_day, code=code)
            if self._is_light:
                pix = render_colored_icon(icon_path, size=20, color="#1e293b")
            else:
                pix = QPixmap(icon_path)
            if not pix.isNull():
                icon_s = 20
                painter.drawPixmap(int(cx - icon_s / 2), int(pad_t - 42), icon_s, icon_s, pix)

            # Temp text above
            painter.setFont(font_temp)
            t_str = format_temp(p.get("temp"), unit=self._temp_unit, show_sign=True)
            painter.setPen(QColor(15, 23, 42) if self._is_light else QColor(248, 250, 252))
            painter.drawText(QRectF(cx - 24, pad_t - 22, 48, 16), Qt.AlignmentFlag.AlignCenter, t_str)

            # Time label below
            painter.setFont(font_time)
            t_lbl = str(p.get("time", ""))
            painter.setPen(QColor(100, 116, 139) if self._is_light else QColor(148, 163, 184))
            painter.drawText(QRectF(cx - 24, h - 38, 48, 16), Qt.AlignmentFlag.AlignCenter, t_lbl)

            # Wind speed and arrow
            w_spd = p.get("wind_speed", 0.0)
            w_dir = p.get("wind_direction", 0)
            painter.setFont(font_wind)
            w_str = f"{round(w_spd)}"
            arrow_sym = self._wind_arrow(w_dir)
            painter.setPen(QColor(2, 132, 199) if self._is_light else QColor(56, 189, 248))
            painter.drawText(QRectF(cx - 24, h - 20, 48, 16), Qt.AlignmentFlag.AlignCenter, f"{arrow_sym} {w_str}")

        # 4. Hover Scrubber Tooltip Card
        if self._hover_idx is not None and 0 <= self._hover_idx < len(coords):
            hx, hy = coords[self._hover_idx]
            p = self._points[self._hover_idx]

            # Vertical guide line
            scrub_pen = QPen(QColor(251, 146, 60, 180), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(scrub_pen)
            painter.drawLine(int(hx), int(pad_t - 4), int(hx), int(h - pad_b + 4))

            # Hover tooltip pill
            tt_w = 120.0
            tt_h = 56.0
            tt_x = max(10.0, min(w - tt_w - 10.0, hx - tt_w / 2.0))
            tt_y = max(10.0, hy - tt_h - 14.0)

            painter.setPen(QPen(QColor(251, 146, 60), 1.2))
            painter.setBrush(QColor(15, 23, 42, 235) if not self._is_light else QColor(255, 255, 255, 240))
            painter.drawRoundedRect(QRectF(tt_x, tt_y, tt_w, tt_h), 8, 8)

            painter.setPen(QColor(248, 250, 252) if not self._is_light else QColor(15, 23, 42))
            f_hdr = QFont("Sans Serif", 9)
            f_hdr.setBold(True)
            painter.setFont(f_hdr)
            tt_title = f"{p.get('time', '')} • {format_temp(p.get('temp'), self._temp_unit)}"
            painter.drawText(QRectF(tt_x + 6, tt_y + 6, tt_w - 12, 16), Qt.AlignmentFlag.AlignLeft, tt_title)

            painter.setFont(QFont("Sans Serif", 8))
            painter.setPen(QColor(148, 163, 184) if not self._is_light else QColor(71, 85, 105))
            c_text = get_condition_text(p.get("code", 0), lang=self._lang, is_day=bool(p.get("is_day", 1)))
            painter.drawText(QRectF(tt_x + 6, tt_y + 24, tt_w - 12, 14), Qt.AlignmentFlag.AlignLeft, c_text)

            w_detail = format_wind_speed(p.get("wind_speed", 0), unit=self._wind_unit, lang=self._lang)
            w_card = cardinal_from_degrees(p.get("wind_direction", 0), lang=self._lang)
            painter.drawText(QRectF(tt_x + 6, tt_y + 38, tt_w - 12, 14), Qt.AlignmentFlag.AlignLeft, f"{w_card} {w_detail}")

    def _paint_daily(self, painter: QPainter, w: int, h: int) -> None:
        """Paint 2 temperature curves (Day and Night) across configured forecast days."""
        if len(self._daily_points) < 1:
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("weather_no_data"))
            return

        pad_l = 44.0
        pad_r = 44.0
        pad_t = 56.0
        pad_b = 58.0
        plot_w = max(10.0, w - pad_l - pad_r)
        plot_h = max(10.0, h - pad_t - pad_b)

        day_temps = [float(p.get("day_temp", 0.0)) for p in self._daily_points]
        night_temps = [float(p.get("night_temp", 0.0)) for p in self._daily_points]
        all_temps = day_temps + night_temps
        min_t = min(all_temps)
        max_t = max(all_temps)
        if max_t - min_t < 4.0:
            max_t += 2.0
            min_t -= 2.0

        n = len(self._daily_points)
        step_x = plot_w / max(1, n - 1)

        coords_day: list[tuple[float, float]] = []
        coords_night: list[tuple[float, float]] = []
        for i in range(n):
            cx = pad_l + i * step_x
            cy_day = pad_t + plot_h - ((day_temps[i] - min_t) / (max_t - min_t)) * plot_h
            cy_night = pad_t + plot_h - ((night_temps[i] - min_t) / (max_t - min_t)) * plot_h
            coords_day.append((cx, cy_day))
            coords_night.append((cx, cy_night))

        # 1. Subtle horizontal temperature grid lines
        grid_pen = QPen(QColor(0, 0, 0, 15) if self._is_light else QColor(255, 255, 255, 15), 1.0)
        painter.setPen(grid_pen)
        for g_frac in (0.0, 0.5, 1.0):
            gy = pad_t + g_frac * plot_h
            painter.drawLine(int(pad_l), int(gy), int(w - pad_r), int(gy))

        # 2. Build Day and Night spline paths
        path_day = self._build_spline_path(coords_day)
        path_night = self._build_spline_path(coords_night)

        # 3. Fills under curves
        fill_base_y = pad_t + plot_h + 10.0
        if len(coords_day) >= 2:
            fill_day = QPainterPath(path_day)
            fill_day.lineTo(coords_day[-1][0], fill_base_y)
            fill_day.lineTo(coords_day[0][0], fill_base_y)
            fill_day.closeSubpath()

            grad_day = QLinearGradient(0, pad_t, 0, fill_base_y)
            if self._is_light:
                grad_day.setColorAt(0.0, QColor(234, 88, 12, 45))
                grad_day.setColorAt(1.0, QColor(234, 88, 12, 0))
            else:
                grad_day.setColorAt(0.0, QColor(251, 146, 60, 55))
                grad_day.setColorAt(1.0, QColor(251, 146, 60, 0))
            painter.fillPath(fill_day, grad_day)

            fill_night = QPainterPath(path_night)
            fill_night.lineTo(coords_night[-1][0], fill_base_y)
            fill_night.lineTo(coords_night[0][0], fill_base_y)
            fill_night.closeSubpath()

            grad_night = QLinearGradient(0, pad_t, 0, fill_base_y)
            if self._is_light:
                grad_night.setColorAt(0.0, QColor(2, 132, 199, 40))
                grad_night.setColorAt(1.0, QColor(2, 132, 199, 0))
            else:
                grad_night.setColorAt(0.0, QColor(56, 189, 248, 50))
                grad_night.setColorAt(1.0, QColor(56, 189, 248, 0))
            painter.fillPath(fill_night, grad_night)

        # 4. Strokes
        day_curve_color = QColor(217, 119, 6) if self._is_light else QColor(251, 146, 60)
        night_curve_color = QColor(2, 132, 199) if self._is_light else QColor(56, 189, 248)

        pen_day = QPen(day_curve_color, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen_day)
        painter.drawPath(path_day)

        pen_night = QPen(night_curve_color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen_night)
        painter.drawPath(path_night)

        # 5. Points and labels
        font_temp_day = QFont("Sans Serif", 9, QFont.Weight.Bold)
        font_temp_night = QFont("Sans Serif", 9, QFont.Weight.Bold)
        font_day_lbl = QFont("Sans Serif", 8, QFont.Weight.Bold)
        font_footer = QFont("Sans Serif", 8)

        day_text_color = QColor(194, 65, 12) if self._is_light else QColor(253, 186, 116)
        night_text_color = QColor(3, 105, 161) if self._is_light else QColor(125, 211, 252)

        for i in range(n):
            cx, cy_d = coords_day[i]
            _, cy_n = coords_night[i]
            p = self._daily_points[i]
            is_hover = (i == self._hover_idx)

            # Dots
            dot_r_d = 5.0 if is_hover else 3.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(day_curve_color)
            painter.drawEllipse(int(cx - dot_r_d), int(cy_d - dot_r_d), int(dot_r_d * 2), int(dot_r_d * 2))
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(int(cx - 1.5), int(cy_d - 1.5), 3, 3)

            dot_r_n = 4.5 if is_hover else 3.0
            painter.setBrush(night_curve_color)
            painter.drawEllipse(int(cx - dot_r_n), int(cy_n - dot_r_n), int(dot_r_n * 2), int(dot_r_n * 2))
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(int(cx - 1.5), int(cy_n - 1.5), 3, 3)

            # Weather Icon
            code = p.get("code", 0)
            icon_path = get_weather_icon_path(code, is_day=1, code=code)
            if self._is_light:
                pix = render_colored_icon(icon_path, size=22, color="#1e293b")
            else:
                pix = QPixmap(icon_path)
            if not pix.isNull():
                painter.drawPixmap(int(cx - 11), int(pad_t - 44), 22, 22, pix)

            # Day temp text above day dot
            painter.setFont(font_temp_day)
            t_day_str = format_temp(p.get("day_temp"), unit=self._temp_unit, show_sign=True)
            painter.setPen(day_text_color)
            painter.drawText(QRectF(cx - 28, cy_d - 18, 56, 16), Qt.AlignmentFlag.AlignCenter, t_day_str)

            # Night temp text below night dot
            painter.setFont(font_temp_night)
            t_night_str = format_temp(p.get("night_temp"), unit=self._temp_unit, show_sign=True)
            painter.setPen(night_text_color)
            painter.drawText(QRectF(cx - 28, cy_n + 6, 56, 16), Qt.AlignmentFlag.AlignCenter, t_night_str)

            # Weekday label below
            painter.setFont(font_day_lbl)
            d_name = str(p.get("day", ""))
            date_s = str(p.get("date", ""))
            painter.setPen(QColor(15, 23, 42) if self._is_light else QColor(248, 250, 252))
            painter.drawText(QRectF(cx - 28, h - 38, 56, 16), Qt.AlignmentFlag.AlignCenter, d_name)

            # Footer label (Date or Precip/Wind)
            painter.setFont(font_footer)
            precip_p = p.get("precip_prob", 0)
            if precip_p and int(precip_p) > 0:
                ft_str = f"🌧 {int(precip_p)}%"
                painter.setPen(QColor(2, 132, 199) if self._is_light else QColor(56, 189, 248))
            elif date_s:
                ft_str = date_s
                painter.setPen(QColor(100, 116, 139) if self._is_light else QColor(148, 163, 184))
            else:
                w_spd = p.get("wind_speed", 0.0)
                w_dir = p.get("wind_direction", 0)
                ft_str = f"{self._wind_arrow(w_dir)} {round(w_spd)}"
                painter.setPen(QColor(100, 116, 139) if self._is_light else QColor(148, 163, 184))
            painter.drawText(QRectF(cx - 28, h - 20, 56, 16), Qt.AlignmentFlag.AlignCenter, ft_str)

        # 6. Hover Tooltip
        if self._hover_idx is not None and 0 <= self._hover_idx < len(coords_day):
            hx, hy_d = coords_day[self._hover_idx]
            _, hy_n = coords_night[self._hover_idx]
            p = self._daily_points[self._hover_idx]

            # Vertical guide line
            scrub_pen = QPen(QColor(251, 146, 60, 180), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(scrub_pen)
            painter.drawLine(int(hx), int(pad_t - 4), int(hx), int(h - pad_b + 4))

            # Tooltip card
            tt_w = 148.0
            tt_h = 66.0
            tt_x = max(10.0, min(w - tt_w - 10.0, hx - tt_w / 2.0))
            tt_y = max(10.0, min(hy_d, hy_n) - tt_h - 14.0)
            if tt_y < 10.0:
                tt_y = max(hy_d, hy_n) + 16.0

            painter.setPen(QPen(day_curve_color, 1.2))
            painter.setBrush(QColor(15, 23, 42, 240) if not self._is_light else QColor(255, 255, 255, 245))
            painter.drawRoundedRect(QRectF(tt_x, tt_y, tt_w, tt_h), 8, 8)

            painter.setPen(QColor(248, 250, 252) if not self._is_light else QColor(15, 23, 42))
            f_hdr = QFont("Sans Serif", 9, QFont.Weight.Bold)
            painter.setFont(f_hdr)
            d_hdr = f"{p.get('day', '')}" + (f", {p.get('date')}" if p.get("date") else "")
            painter.drawText(QRectF(tt_x + 8, tt_y + 6, tt_w - 16, 16), Qt.AlignmentFlag.AlignLeft, d_hdr)

            painter.setFont(QFont("Sans Serif", 8))
            painter.setPen(QColor(148, 163, 184) if not self._is_light else QColor(71, 85, 105))
            c_text = get_condition_text(p.get("code", 0), lang=self._lang, is_day=True)
            painter.drawText(QRectF(tt_x + 8, tt_y + 24, tt_w - 16, 14), Qt.AlignmentFlag.AlignLeft, c_text)

            painter.setFont(QFont("Sans Serif", 8, QFont.Weight.Bold))
            t_day_fmt = format_temp(p.get("day_temp"), unit=self._temp_unit, show_sign=True)
            t_night_fmt = format_temp(p.get("night_temp"), unit=self._temp_unit, show_sign=True)
            day_lbl, night_lbl = self._day_night_labels(self._lang)
            painter.setPen(day_text_color)
            painter.drawText(QRectF(tt_x + 8, tt_y + 42, 68, 16), Qt.AlignmentFlag.AlignLeft, f"{day_lbl}: {t_day_fmt}")
            painter.setPen(night_text_color)
            painter.drawText(QRectF(tt_x + 78, tt_y + 42, 68, 16), Qt.AlignmentFlag.AlignLeft, f"{night_lbl}: {t_night_fmt}")

    @staticmethod
    def _wind_arrow(deg: float | int) -> str:
        """Arrow indicating direction wind is blowing to."""
        d = (deg + 180) % 360
        arrows = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
        idx = int((d + 22.5) / 45.0) % 8
        return arrows[idx]


class BarometerChartWidget(QWidget):
    """Atmospheric pressure trend supporting 24h hourly and multi-day daily views."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._points: list[float] = []
        self._time_labels: list[str] = []
        self._press_unit = "mmHg"
        self._lang = "ru"
        self._is_light = False

    def set_theme_light(self, is_light: bool) -> None:
        self._is_light = is_light
        self.update()

    def update_data(
        self,
        pressures: list[float],
        times: list[str],
        press_unit: str = "mmHg",
        lang: str = "ru",
        is_light: bool = False,
    ) -> None:
        self._points = pressures
        self._time_labels = times
        self._press_unit = press_unit
        self._lang = lang
        self._is_light = is_light
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        if len(self._points) < 2:
            return

        pad_l = 36.0
        pad_r = 44.0
        pad_t = 20.0
        pad_b = 26.0
        plot_w = max(10.0, w - pad_l - pad_r)
        plot_h = max(10.0, h - pad_t - pad_b)

        min_p = min(self._points)
        max_p = max(self._points)
        if max_p - min_p < 2.0:
            max_p += 1.0
            min_p -= 1.0

        n = len(self._points)
        step_x = plot_w / max(1, n - 1)

        coords: list[tuple[float, float]] = []
        for i, val in enumerate(self._points):
            cx = pad_l + i * step_x
            cy = pad_t + plot_h - ((val - min_p) / (max_p - min_p)) * plot_h
            coords.append((cx, cy))

        # Y-axis pressure lines and labels
        painter.setFont(QFont("Sans Serif", 8))
        for p_val in (min_p, (min_p + max_p) / 2.0, max_p):
            cy = pad_t + plot_h - ((p_val - min_p) / (max_p - min_p)) * plot_h
            painter.setPen(QColor(0, 0, 0, 15) if self._is_light else QColor(255, 255, 255, 15))
            painter.drawLine(int(pad_l), int(cy), int(w - pad_r), int(cy))

            painter.setPen(QColor(100, 116, 139) if self._is_light else QColor(148, 163, 184))
            val_str = f"{int(round(p_val))}"
            painter.drawText(QRectF(w - pad_r + 4, cy - 8, 36, 16), Qt.AlignmentFlag.AlignLeft, val_str)

        # Smooth spline
        path = QPainterPath()
        path.moveTo(coords[0][0], coords[0][1])
        for i in range(len(coords) - 1):
            p0 = coords[max(0, i - 1)]
            p1 = coords[i]
            p2 = coords[i + 1]
            p3 = coords[min(len(coords) - 1, i + 2)]

            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])

        # Fill under curve
        fill_path = QPainterPath(path)
        fill_path.lineTo(coords[-1][0], pad_t + plot_h + 4)
        fill_path.lineTo(coords[0][0], pad_t + plot_h + 4)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, pad_t, 0, pad_t + plot_h)
        if self._is_light:
            grad.setColorAt(0.0, QColor(99, 102, 241, 70))
            grad.setColorAt(1.0, QColor(99, 102, 241, 5))
            stroke_clr = QColor(79, 70, 229)
        else:
            grad.setColorAt(0.0, QColor(129, 140, 248, 80))
            grad.setColorAt(1.0, QColor(129, 140, 248, 5))
            stroke_clr = QColor(129, 140, 248)

        painter.fillPath(fill_path, grad)

        painter.setPen(QPen(stroke_clr, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

        # Dots and value labels when n <= 10 (e.g. daily view)
        if n <= 10:
            painter.setFont(QFont("Sans Serif", 8, QFont.Weight.Bold))
            for i, (cx, cy) in enumerate(coords):
                painter.setBrush(stroke_clr)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(int(cx - 3.5), int(cy - 3.5), 7, 7)
                painter.setBrush(QColor(255, 255, 255))
                painter.drawEllipse(int(cx - 1.5), int(cy - 1.5), 3, 3)

                val_str = f"{self._points[i]:.0f}"
                painter.setPen(QColor(129, 140, 248) if not self._is_light else QColor(79, 70, 229))
                painter.drawText(QRectF(cx - 20, cy - 18, 40, 14), Qt.AlignmentFlag.AlignCenter, val_str)

        # Time / Day labels
        step_disp = 1 if n <= 10 else 4
        painter.setFont(QFont("Sans Serif", 8))
        painter.setPen(QColor(100, 116, 139) if self._is_light else QColor(148, 163, 184))
        for i in range(0, n, step_disp):
            cx = coords[i][0]
            if i < len(self._time_labels):
                t_lbl = self._time_labels[i]
                painter.drawText(QRectF(cx - 24, h - 18, 48, 16), Qt.AlignmentFlag.AlignCenter, t_lbl)


class GeomagneticChartWidget(QWidget):
    """Kp-index bar chart: 3-hour bins (24h) or daily maxima (X days)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._bars: list[dict[str, Any]] = []
        self._is_light = False

    def set_theme_light(self, is_light: bool) -> None:
        self._is_light = is_light
        self.update()

    def update_bars(self, bars: list[dict[str, Any]], is_light: bool = False) -> None:
        self._bars = bars
        self._is_light = is_light
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        if not self._bars:
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("weather_no_data"))
            return

        pad_l = 30.0
        pad_r = 12.0
        pad_t = 16.0
        pad_b = 26.0
        plot_w = max(10.0, w - pad_l - pad_r)
        plot_h = max(10.0, h - pad_t - pad_b)

        # Kp scale is fixed 0..9
        kp_max = 9.0

        # Horizontal Kp grid lines (0, 3, 6, 9)
        painter.setFont(QFont("Sans Serif", 8))
        for kp_grid in (0.0, 3.0, 6.0, 9.0):
            cy = pad_t + plot_h - (kp_grid / kp_max) * plot_h
            painter.setPen(QColor(0, 0, 0, 15) if self._is_light else QColor(255, 255, 255, 15))
            painter.drawLine(int(pad_l), int(cy), int(w - pad_r), int(cy))
            painter.setPen(QColor(100, 116, 139) if self._is_light else QColor(148, 163, 184))
            painter.drawText(QRectF(0, cy - 8, pad_l - 6, 16), Qt.AlignmentFlag.AlignRight, f"{int(kp_grid)}")

        n = len(self._bars)
        slot = plot_w / max(1, n)
        bar_w = max(6.0, min(28.0, slot * 0.62))

        show_labels = n <= 12
        for i, bar in enumerate(self._bars):
            kp_val = float(bar.get("kp", 0.0))
            kp_val = max(0.0, min(kp_max, kp_val))
            cx = pad_l + slot * (i + 0.5)
            bh = (kp_val / kp_max) * plot_h
            by = pad_t + plot_h - bh

            bar_color = QColor(str(bar.get("color", "#22c55e")))
            if not bar_color.isValid():
                bar_color = QColor("#22c55e")

            # Forecast bins are drawn softer than observed ones
            if bar.get("is_forecast", False):
                bar_color.setAlpha(210)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bar_color)
            painter.drawRoundedRect(QRectF(cx - bar_w / 2.0, by, bar_w, bh), 3, 3)

            # Kp value above each bar
            painter.setFont(QFont("Sans Serif", 7, QFont.Weight.Bold))
            painter.setPen(QColor(100, 116, 139) if self._is_light else QColor(148, 163, 184))
            painter.drawText(
                QRectF(cx - 20, by - 15, 40, 14),
                Qt.AlignmentFlag.AlignCenter,
                f"{kp_val:.1f}",
            )

            # Time / day label below
            if show_labels:
                painter.setFont(QFont("Sans Serif", 8))
                painter.setPen(QColor(100, 116, 139) if self._is_light else QColor(148, 163, 184))
                painter.drawText(
                    QRectF(cx - 24, h - 18, 48, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    str(bar.get("label", "")),
                )


class ClimateNormsWidget(QWidget):
    """Screen 2: Copernicus ERA5 30-Year Climate Normals vs Current Weather."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_light = False

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 14, 14, 14)
        self.main_layout.setSpacing(14)

        # 1. Comparison Card (Current Month Fact vs 30-Year Normal)
        self.card_compare = QFrame()
        self.card_compare.setObjectName("ClimateCard")
        l_comp = QVBoxLayout(self.card_compare)
        l_comp.setContentsMargins(16, 14, 16, 14)
        l_comp.setSpacing(10)

        self.lbl_compare_title = QLabel(t("climate_card_title"))
        self.lbl_compare_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        l_comp.addWidget(self.lbl_compare_title)

        self.lbl_month_hdr = QLabel("Октябрь • Климатическая норма ERA5")
        self.lbl_month_hdr.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        l_comp.addWidget(self.lbl_month_hdr)

        row_stat = QHBoxLayout()
        row_stat.setSpacing(12)

        self.box_fact = QFrame()
        self.box_fact.setObjectName("ClimateStatBox")
        l_fact = QVBoxLayout(self.box_fact)
        l_fact.setContentsMargins(10, 8, 10, 8)
        self.lbl_fact_title = QLabel(t("climate_current_temp", val=0))
        self.lbl_fact_val = QLabel("+12°")
        self.lbl_fact_val.setStyleSheet("font-size: 24px; font-weight: bold;")
        l_fact.addWidget(self.lbl_fact_title)
        l_fact.addWidget(self.lbl_fact_val)
        row_stat.addWidget(self.box_fact)

        self.box_norm = QFrame()
        self.box_norm.setObjectName("ClimateStatBox")
        l_norm = QVBoxLayout(self.box_norm)
        l_norm.setContentsMargins(10, 8, 10, 8)
        self.lbl_norm_title = QLabel(t("climate_norm_range", min=0, max=0))
        self.lbl_norm_val = QLabel("+3° … +9°")
        self.lbl_norm_val.setStyleSheet("font-size: 24px; font-weight: bold; color: #38bdf8;")
        l_norm.addWidget(self.lbl_norm_title)
        l_norm.addWidget(self.lbl_norm_val)
        row_stat.addWidget(self.box_norm)

        self.box_anomaly = QFrame()
        self.box_anomaly.setObjectName("ClimateStatBox")
        l_anom = QVBoxLayout(self.box_anomaly)
        l_anom.setContentsMargins(10, 8, 10, 8)
        self.lbl_anom_title = QLabel(t("climate_anomaly_title"))
        self.lbl_anom_val = QLabel("+6.0°C выше нормы")
        self.lbl_anom_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #fb923c;")
        l_anom.addWidget(self.lbl_anom_title)
        l_anom.addWidget(self.lbl_anom_val)
        row_stat.addWidget(self.box_anomaly)

        l_comp.addLayout(row_stat)

        self.lbl_precip_norm = QLabel("Месячная норма осадков: 59 мм")
        self.lbl_precip_norm.setStyleSheet("font-size: 12px; color: #94a3b8;")
        l_comp.addWidget(self.lbl_precip_norm)

        self.main_layout.addWidget(self.card_compare)

        # 2. 12-Month Annual Profile Table
        self.card_table = QFrame()
        self.card_table.setObjectName("ClimateCard")
        l_table = QVBoxLayout(self.card_table)
        l_table.setContentsMargins(16, 14, 16, 14)
        l_table.setSpacing(8)

        self.lbl_tbl_title = QLabel(t("climate_annual_table_title"))
        self.lbl_tbl_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        l_table.addWidget(self.lbl_tbl_title)

        self.table_scroll = QScrollArea()
        self.table_scroll.setWidgetResizable(True)
        self.table_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.table_scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }")
        self.table_scroll.viewport().setStyleSheet("background: transparent;")
        self.table_container = QWidget()
        self.table_container.setStyleSheet("background: transparent;")
        self.table_layout = QVBoxLayout(self.table_container)
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        self.table_layout.setSpacing(4)
        self.table_scroll.setWidget(self.table_container)
        l_table.addWidget(self.table_scroll)

        self.main_layout.addWidget(self.card_table, 1)

        # 3. Attribution footer
        self.lbl_attribution = QLabel(t("climate_attribution_label"))
        self.lbl_attribution.setStyleSheet("font-size: 10px; color: #64748b; padding: 2px;")
        self.lbl_attribution.setWordWrap(True)
        self.main_layout.addWidget(self.lbl_attribution)

    def retranslate_ui(self) -> None:
        self.lbl_compare_title.setText(t("climate_card_title"))
        self.lbl_anom_title.setText(t("climate_anomaly_title"))
        self.lbl_tbl_title.setText(t("climate_annual_table_title"))
        self.lbl_attribution.setText(t("climate_attribution_label"))

    def set_theme_light(self, is_light: bool) -> None:
        self._is_light = is_light
        card_bg = "rgba(0, 0, 0, 0.04)" if is_light else "rgba(255, 255, 255, 0.05)"
        card_border = "rgba(0, 0, 0, 0.12)" if is_light else "rgba(255, 255, 255, 0.12)"
        box_bg = "rgba(0, 0, 0, 0.03)" if is_light else "rgba(255, 255, 255, 0.03)"
        text_primary = "#0f172a" if is_light else "#f8fafc"

        self.setStyleSheet(f"""
            QFrame#ClimateCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 12px;
            }}
            QFrame#ClimateStatBox {{
                background-color: {box_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text_primary};
            }}
        """)

    def update_climate_data(self, data: WeatherForecastData, lang: str = "ru", is_light: bool = False) -> None:
        self.set_theme_light(is_light)
        baseline = get_era5_baseline()
        monthly = baseline.get("monthly", [])
        if not monthly:
            return

        lat = data.lat or 55.0
        lon = data.lon or 37.6
        now_dt = datetime.now(timezone.utc)
        cur_m = now_dt.month
        cur_temp = data.current.temp if data.current else 15.0

        # Adjust ERA5 monthly baseline for target lat/lon (Copernicus 0.25° adjustment)
        lat_diff = (55.0 - lat) * 0.7
        cont_diff = 0.0
        if 60.0 <= lon <= 110.0 and lat > 50.0:
            if cur_m in (11, 12, 1, 2):
                cont_diff = -7.0
            elif cur_m in (10, 3):
                cont_diff = -2.0
            elif cur_m in (6, 7, 8):
                cont_diff = 1.0
        elif lat < 45.0:
            lat_diff = (55.0 - lat) * 1.1

        m_name = get_month_name(cur_m, short=False, lang=lang)
        self.lbl_month_hdr.setText(f"{m_name.capitalize()} • ERA5 (1991–2020) — {data.city_name}")

        # Current month adjusted bounds
        cur_row = monthly[cur_m - 1]
        norm_min = round(float(cur_row.get("temp_min", 0.0)) + lat_diff + cont_diff)
        norm_max = round(float(cur_row.get("temp_max", 10.0)) + lat_diff + cont_diff)
        if norm_min >= norm_max:
            norm_max = norm_min + 4
        norm_avg = (norm_min + norm_max) / 2.0

        self.lbl_fact_title.setText(t("climate_current_temp", val=round(cur_temp)))
        self.lbl_fact_val.setText(f"{round(cur_temp):+d}°")

        self.lbl_norm_title.setText(t("climate_norm_range", min=norm_min, max=norm_max))
        self.lbl_norm_val.setText(f"{norm_min:+d}° … {norm_max:+d}°")

        diff = cur_temp - norm_avg
        if diff >= 1.0:
            self.lbl_anom_val.setText(t("climate_above_norm", val=diff))
            self.lbl_anom_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #fb923c;")
        elif diff <= -1.0:
            self.lbl_anom_val.setText(t("climate_below_norm", val=abs(diff)))
            self.lbl_anom_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        else:
            self.lbl_anom_val.setText(t("climate_near_norm", val=diff))
            self.lbl_anom_val.setStyleSheet("font-size: 16px; font-weight: bold; color: #10b981;")

        p_mm = cur_row.get("precip_mm", 50)
        self.lbl_precip_norm.setText(t("climate_precip_norm", val=p_mm))

        # Rebuild 12-month annual table
        while self.table_layout.count():
            item = self.table_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, row in enumerate(monthly):
            m_num = idx + 1
            is_active_m = (m_num == cur_m)
            m_short = get_month_name(m_num, short=True, lang=lang).capitalize()

            adj_min = round(float(row.get("temp_min", 0.0)) + lat_diff + cont_diff)
            adj_max = round(float(row.get("temp_max", 10.0)) + lat_diff + cont_diff)
            if adj_min >= adj_max:
                adj_max = adj_min + 4
            adj_precip = row.get("precip_mm", 40)

            row_frame = QFrame()
            row_frame.setFixedHeight(28)
            if is_active_m:
                bg_active = "rgba(56, 189, 248, 0.18)" if not is_light else "rgba(2, 132, 199, 0.15)"
                border_active = "#38bdf8" if not is_light else "#0284c7"
                row_frame.setStyleSheet(f"background-color: {bg_active}; border: 1px solid {border_active}; border-radius: 6px;")
            else:
                row_frame.setStyleSheet("background: transparent; border: none;")

            row_l = QHBoxLayout(row_frame)
            row_l.setContentsMargins(8, 2, 8, 2)
            row_l.setSpacing(8)

            lbl_m = QLabel(m_short)
            lbl_m.setFixedWidth(50)
            if is_active_m:
                lbl_m.setStyleSheet("font-weight: bold; color: #38bdf8;" if not is_light else "font-weight: bold; color: #0284c7;")
            row_l.addWidget(lbl_m)

            lbl_min_str = QLabel(f"{adj_min:+d}°")
            lbl_min_str.setFixedWidth(36)
            lbl_min_str.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_l.addWidget(lbl_min_str)

            # Capsule progress visualization
            bar = QWidget()
            bar.setFixedHeight(6)
            bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar_color = "#38bdf8" if adj_max <= 10 else ("#10b981" if adj_max <= 20 else "#fb923c")
            bar.setStyleSheet(f"background-color: {bar_color}; border-radius: 3px;")
            row_l.addWidget(bar, 1)

            lbl_max_str = QLabel(f"{adj_max:+d}°")
            lbl_max_str.setFixedWidth(36)
            lbl_max_str.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            row_l.addWidget(lbl_max_str)

            lbl_pr = QLabel(f"{adj_precip} мм")
            lbl_pr.setFixedWidth(56)
            lbl_pr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_pr.setStyleSheet("color: #64748b;" if is_light else "color: #94a3b8;")
            row_l.addWidget(lbl_pr)

            self.table_layout.addWidget(row_frame)

        self.table_layout.addStretch(1)



class GlanceableTab(QFrame):
    """Interactive glanceable tab button for the right-hand analytics rail.

    Displays:
    - Left: Icon (e.g. 🌡️, ⏱️, ⚡, 🌍, 🧭)
    - Center/Right: Vertical text block:
        - Title (localized section name)
        - Live Glanceable Metric (e.g. "+18°C (+12°..+21°)", "754 мм ↗", "Kp 2.0 (Штиль)")
    """

    clicked = QtCore.Signal(int)

    def __init__(
        self,
        index: int,
        icon_char: str,
        title: str,
        initial_metric: str = "—",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self._icon_char = icon_char
        self._title = title
        self._metric = initial_metric
        self._is_active = False
        self._is_light = False

        self.setObjectName("GlanceableTab")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # Icon
        self.lbl_icon = QLabel(self._icon_char, self)
        self.lbl_icon.setObjectName("GlanceableTabIcon")
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setFixedWidth(24)
        self.lbl_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.lbl_icon)

        # Text column
        v_box = QVBoxLayout()
        v_box.setContentsMargins(0, 0, 0, 0)
        v_box.setSpacing(2)

        self.lbl_title = QLabel(self._title, self)
        self.lbl_title.setObjectName("GlanceableTabTitle")
        self.lbl_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        v_box.addWidget(self.lbl_title)

        self.lbl_metric = QLabel(self._metric, self)
        self.lbl_metric.setObjectName("GlanceableTabMetric")
        self.lbl_metric.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        v_box.addWidget(self.lbl_metric)

        layout.addLayout(v_box, 1)

        self._update_styles()

    def mousePressEvent(self, event: Any) -> None:
        if hasattr(event, "button") and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)
        super().mousePressEvent(event)

    def set_active(self, active: bool) -> None:
        if self._is_active != active:
            self._is_active = active
            self._update_styles()

    def set_theme_light(self, is_light: bool) -> None:
        self._is_light = is_light
        self._update_styles()

    def update_content(self, title: str | None = None, metric: str | None = None) -> None:
        if title is not None and title != self._title:
            self._title = title
            self.lbl_title.setText(title)
        if metric is not None and metric != self._metric:
            self._metric = metric
            self.lbl_metric.setText(metric)

    def _update_styles(self) -> None:
        if self._is_active:
            self.setStyleSheet("""
                QFrame#GlanceableTab {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #0284c7, stop:1 #38bdf8);
                    border: 1px solid rgba(255, 255, 255, 0.40);
                    border-radius: 10px;
                }
                QLabel#GlanceableTabIcon {
                    font-size: 18px;
                    background: transparent;
                }
                QLabel#GlanceableTabTitle {
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    background: transparent;
                }
                QLabel#GlanceableTabMetric {
                    color: #f0f9ff;
                    font-weight: 600;
                    font-size: 11px;
                    background: transparent;
                }
            """)
        else:
            if self._is_light:
                bg = "rgba(0, 0, 0, 0.03)"
                bg_hover = "rgba(0, 0, 0, 0.07)"
                border = "rgba(0, 0, 0, 0.08)"
                border_hover = "rgba(2, 132, 199, 0.40)"
                col_title = "#0f172a"
                col_metric = "#475569"
            else:
                bg = "rgba(255, 255, 255, 0.04)"
                bg_hover = "rgba(255, 255, 255, 0.08)"
                border = "rgba(255, 255, 255, 0.08)"
                border_hover = "rgba(56, 189, 248, 0.40)"
                col_title = "#f8fafc"
                col_metric = "#94a3b8"

            self.setStyleSheet(f"""
                QFrame#GlanceableTab {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 10px;
                }}
                QFrame#GlanceableTab:hover {{
                    background-color: {bg_hover};
                    border: 1px solid {border_hover};
                }}
                QLabel#GlanceableTabIcon {{
                    font-size: 18px;
                    background: transparent;
                }}
                QLabel#GlanceableTabTitle {{
                    color: {col_title};
                    font-weight: 600;
                    font-size: 12px;
                    background: transparent;
                }}
                QLabel#GlanceableTabMetric {{
                    color: {col_metric};
                    font-size: 11px;
                    background: transparent;
                }}
            """)


class DetailedForecastDialogQt(QDialog):

    """Detailed weather forecast dialog with 2 focused views switched via LMB click."""

    def __init__(
        self,
        parent: QWidget | None,
        config_manager: Any,
        data: WeatherForecastData | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window)
        self.config_manager = config_manager
        self._data = data

        self._temp_press_period: str = "24h"
        self._points_24: list[dict[str, Any]] = []
        self._daily_points: list[dict[str, Any]] = []
        self._press_vals_24: list[float] = []
        self._time_labels_24: list[str] = []
        self._press_vals_daily: list[float] = []
        self._time_labels_daily: list[str] = []

        self.setWindowTitle(t("detailed_title", city=data.city_name if data else "—"))
        # Fallback bounds until _fit_static_size() computes the real static size.
        self.setMinimumSize(880, 520)

        self._last_switch_ts: float = 0.0
        self._static_size_fitted: bool = False

        self._build_ui()
        self._fit_static_size()
        if self._data:
            self.update_data(self._data)
            # Live data can raise the panes' minimum heights (e.g. the wind
            # rose with real observations); re-fit so nothing gets clipped.
            self._fit_static_size()

    def _fit_static_size(self) -> None:
        """Size the window once to the tallest pane so switching never resizes it.

        Each pane holds a single card; the shared 24h/X-days bar adds height
        only on the temperature, pressure and geomagnetic panes. Rather than
        re-deriving the layout arithmetic by hand (which drifts a few pixels
        off and clips the tallest pane), measure the layout's own minimum in
        both bar states and take the worst case, so the window is static and
        no pane is ever clipped. The user can enlarge it, but not shrink
        below content.
        """
        lay = self.layout()
        if lay is None:
            return
        bar = getattr(self, "period_bar", None)

        def _measure(bar_visible: bool) -> int:
            if bar is not None:
                bar.setVisible(bar_visible)
            lay.invalidate()
            lay.activate()
            return lay.minimumSize().height()

        # Bar hidden: QStackedWidget.minimumSizeHint covers EVERY pane, so
        # this is the requirement of the climate / wind-rose panes.
        hidden_h = _measure(False)
        # Bar visible: the layout minimum again counts every pane inside the
        # stack; subtract that and add only the panes that really show the
        # bar, otherwise the bar's height would be charged to panes that
        # never display it.
        shown_h = _measure(True)
        stack_min = self.stack.minimumSizeHint().height()
        bar_pane_max = max(
            (
                self.stack.widget(i).minimumSizeHint().height()
                for i in self._period_bar_panes
                if i < self.stack.count()
            ),
            default=0,
        )
        with_bar_h = max(0, shown_h - stack_min) + bar_pane_max

        # Restore visibility for the pane that is actually current.
        if bar is not None:
            bar.setVisible(self.stack.currentIndex() in self._period_bar_panes)
            lay.invalidate()
            lay.activate()

        needed_h = max(hidden_h, with_bar_h)
        needed_w = max(880, lay.minimumSize().width())
        if needed_h <= 0:
            return

        # Static: minimum equals content size, so the window cannot shrink
        # enough to clip a pane. The first fit sets the exact size; later
        # fits (after live data) only grow, so a manual enlargement sticks.
        self.setMinimumSize(needed_w, needed_h)
        if self._static_size_fitted:
            self.resize(max(self.width(), needed_w), max(self.height(), needed_h))
        else:
            self._static_size_fitted = True
            self.resize(needed_w, needed_h)

    def _get_forecast_days_count(self) -> int:
        """Read configured multi-day forecast length from Options."""
        if self.config_manager:
            v = self.config_manager.get("view_blocks", {})
            if isinstance(v, dict):
                b = v.get("daily", {})
                if isinstance(b, dict) and "days" in b:
                    try:
                        return max(1, min(10, int(b["days"])))
                    except (ValueError, TypeError):
                        pass
        return 5

    @staticmethod
    def _format_days_tab_label(days: int, lang: str = "ru") -> str:
        """Format pluralized tab label for configured days count."""
        if lang == "en":
            return f"{days} day" if days == 1 else f"{days} days"
        elif lang == "uk":
            if days % 10 == 1 and days % 100 != 11:
                return f"{days} день"
            elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
                return f"{days} дні"
            else:
                return f"{days} днів"
        else:  # ru
            if days % 10 == 1 and days % 100 != 11:
                return f"{days} день"
            elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
                return f"{days} дня"
            else:
                return f"{days} дней"

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 14)
        main_layout.setSpacing(10)

        # 1. Top Header Row: City, Condition summary, Screen Badge, and Close button
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.lbl_city_title = QLabel(self._data.city_name if self._data else "—")
        self.lbl_city_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_row.addWidget(self.lbl_city_title)

        self.lbl_cond_summary = QLabel("")
        self.lbl_cond_summary.setStyleSheet("font-size: 13px; color: #94a3b8; font-weight: 500;")
        header_row.addWidget(self.lbl_cond_summary)

        header_row.addStretch(1)

        # ▲/▼ pane switcher (replaces the old click-anywhere cycling)
        self.btn_pane_prev = QPushButton("▲")
        self.btn_pane_prev.setObjectName("BtnPaneNav")
        self.btn_pane_prev.setToolTip(t("switch_prev_pane"))
        self.btn_pane_prev.setFixedSize(30, 30)
        self.btn_pane_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pane_prev.clicked.connect(self.prev_screen)
        header_row.addWidget(self.btn_pane_prev)

        self.btn_pane_next = QPushButton("▼")
        self.btn_pane_next.setObjectName("BtnPaneNav")
        self.btn_pane_next.setToolTip(t("switch_next_pane"))
        self.btn_pane_next.setFixedSize(30, 30)
        self.btn_pane_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pane_next.clicked.connect(self.next_screen)
        header_row.addWidget(self.btn_pane_next)

        self.lbl_screen_badge = QLabel("")
        self.lbl_screen_badge.setObjectName("ScreenBadge")
        header_row.addWidget(self.lbl_screen_badge)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("BtnClose")
        self.btn_close.setToolTip(t("btn_close"))
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        header_row.addWidget(self.btn_close)

        main_layout.addLayout(header_row)

        # 2. Shared period switcher (24h / X days): used by the temperature,
        # pressure and geomagnetic panes; hidden on climate / wind-rose panes.
        self.period_bar = QFrame()
        self.period_bar.setObjectName("TempPressPeriodBar")
        p_layout = QHBoxLayout(self.period_bar)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(8)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_period_24h = QPushButton(t("forecast_tab_24h"), self.period_bar)
        self.btn_period_24h.setObjectName("BtnPeriod24h")
        self.btn_period_24h.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_period_24h.setFixedHeight(30)
        self.btn_period_24h.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.btn_period_24h.clicked.connect(lambda: self.set_temp_press_period("24h"))
        p_layout.addWidget(self.btn_period_24h)

        days_count = self._get_forecast_days_count()
        app_lang = self.config_manager.get("app_language", "ru") if self.config_manager else "ru"
        self.btn_period_daily = QPushButton(self._format_days_tab_label(days_count, app_lang), self.period_bar)
        self.btn_period_daily.setObjectName("BtnPeriodDaily")
        self.btn_period_daily.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_period_daily.setFixedHeight(30)
        self.btn_period_daily.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.btn_period_daily.clicked.connect(lambda: self.set_temp_press_period("daily"))
        p_layout.addWidget(self.btn_period_daily)

        # 3. Stacked panes: one information type per pane, switched by ▲/▼ or right-side tabs.
        self.stack = QStackedWidget()
        self.stack.setObjectName("DetailStack")
        self._period_bar_panes = (0, 1, 2)  # panes that use the period bar

        # Pane 0: Temperature
        self.pane_temperature = QWidget()
        self.pane_temperature.setObjectName("DetailPane")
        l_temp = QVBoxLayout(self.pane_temperature)
        l_temp.setContentsMargins(0, 0, 0, 0)
        l_temp.setSpacing(0)

        # Spline box
        self.frame_spline = QFrame()
        self.frame_spline.setObjectName("DetailedCard")
        l_fs = QVBoxLayout(self.frame_spline)
        l_fs.setContentsMargins(14, 12, 14, 10)
        l_fs.setSpacing(6)

        row_spline_hdr = QHBoxLayout()
        self.lbl_spline_title = QLabel(t("chart_hourly_spline_title"))
        self.lbl_spline_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        row_spline_hdr.addWidget(self.lbl_spline_title)
        row_spline_hdr.addStretch(1)

        self.lbl_legend_day = QLabel("● " + t("forecast_legend_day"))
        self.lbl_legend_day.setStyleSheet("font-size: 11px; font-weight: bold; color: #fb923c;")
        self.lbl_legend_day.setVisible(False)
        row_spline_hdr.addWidget(self.lbl_legend_day)

        self.lbl_legend_night = QLabel("● " + t("forecast_legend_night"))
        self.lbl_legend_night.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        self.lbl_legend_night.setVisible(False)
        row_spline_hdr.addWidget(self.lbl_legend_night)

        l_fs.addLayout(row_spline_hdr)

        self.spline_widget = HourlySplineChartWidget()
        l_fs.addWidget(self.spline_widget, 1)
        l_temp.addWidget(self.frame_spline, 1)
        self.stack.addWidget(self.pane_temperature)

        # Pane 1: Pressure
        self.pane_pressure = QWidget()
        self.pane_pressure.setObjectName("DetailPane")
        l_press = QVBoxLayout(self.pane_pressure)
        l_press.setContentsMargins(0, 0, 0, 0)
        l_press.setSpacing(0)

        # Barometer box
        self.frame_baro = QFrame()
        self.frame_baro.setObjectName("DetailedCard")
        l_fb = QVBoxLayout(self.frame_baro)
        l_fb.setContentsMargins(14, 12, 14, 10)
        l_fb.setSpacing(6)

        row_baro_hdr = QHBoxLayout()
        self.lbl_baro_title = QLabel(t("chart_pressure_title"))
        self.lbl_baro_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        row_baro_hdr.addWidget(self.lbl_baro_title)

        row_baro_hdr.addStretch(1)

        self.lbl_tendency_pill = QLabel("Стабильно →")
        self.lbl_tendency_pill.setFixedHeight(22)
        self.lbl_tendency_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_tendency_pill.setStyleSheet("""
            background-color: rgba(100, 116, 139, 0.20);
            color: #94a3b8;
            font-weight: bold;
            font-size: 11px;
            padding: 2px 10px;
            border-radius: 11px;
            border: 1px solid rgba(100, 116, 139, 0.40);
        """)
        row_baro_hdr.addWidget(self.lbl_tendency_pill)

        self.lbl_baro_curr = QLabel("752 мм рт. ст.")
        self.lbl_baro_curr.setStyleSheet("font-size: 12px; font-weight: bold; color: #818cf8;")
        row_baro_hdr.addWidget(self.lbl_baro_curr)

        l_fb.addLayout(row_baro_hdr)

        self.baro_widget = BarometerChartWidget()
        l_fb.addWidget(self.baro_widget, 1)
        l_press.addWidget(self.frame_baro, 1)
        self.stack.addWidget(self.pane_pressure)

        # Pane 2: Geomagnetic
        self.pane_geomagnetic = QWidget()
        self.pane_geomagnetic.setObjectName("DetailPane")
        l_geo = QVBoxLayout(self.pane_geomagnetic)
        l_geo.setContentsMargins(0, 0, 0, 0)
        l_geo.setSpacing(0)

        # Geomagnetic forecast box (NOAA SWPC Kp-index)
        self.frame_geomag = QFrame()
        self.frame_geomag.setObjectName("DetailedCard")
        l_fg = QVBoxLayout(self.frame_geomag)
        l_fg.setContentsMargins(14, 12, 14, 10)
        l_fg.setSpacing(6)

        row_geomag_hdr = QHBoxLayout()
        self.lbl_geomag_title = QLabel(t("chart_geomagnetic_title"))
        self.lbl_geomag_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        row_geomag_hdr.addWidget(self.lbl_geomag_title)
        row_geomag_hdr.addStretch(1)

        self.lbl_geomag_max = QLabel("—")
        self.lbl_geomag_max.setFixedHeight(22)
        self.lbl_geomag_max.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_geomag_max.setStyleSheet("""
            background-color: rgba(100, 116, 139, 0.20);
            color: #94a3b8;
            font-weight: bold;
            font-size: 11px;
            padding: 2px 10px;
            border-radius: 11px;
            border: 1px solid rgba(100, 116, 139, 0.40);
        """)
        row_geomag_hdr.addWidget(self.lbl_geomag_max)

        l_fg.addLayout(row_geomag_hdr)

        self.geomag_widget = GeomagneticChartWidget()
        l_fg.addWidget(self.geomag_widget, 1)
        l_geo.addWidget(self.frame_geomag, 1)
        self.stack.addWidget(self.pane_geomagnetic)

        # Pane 3: Climate Normals (ERA5)
        self.climate_widget = ClimateNormsWidget()
        self.climate_widget.setObjectName("DetailPane")
        self.stack.addWidget(self.climate_widget)

        # Pane 4: 16-ray Stacked Wind Rose
        self.wind_rose_widget = FullWindRoseWidget(parent=self, config_manager=self.config_manager)
        self.wind_rose_widget.setObjectName("DetailPane")
        self.stack.addWidget(self.wind_rose_widget)

        # Plain QWidgets only paint a stylesheet background with this flag;
        # without it the system palette (light) shows through in dark theme.
        for i in range(self.stack.count()):
            self.stack.widget(i).setAttribute(
                Qt.WidgetAttribute.WA_StyledBackground, True
            )

        # 2. Body: Left Column (Period Bar + Stacked Panes) and Right Glanceable Rail
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(10)
        left_col.addWidget(self.period_bar)
        left_col.addWidget(self.stack, 1)
        body_layout.addLayout(left_col, 1)

        # Right Column: Glanceable Tab Rail (Variant 3)
        self.tab_rail = QFrame()
        self.tab_rail.setObjectName("GlanceableTabRail")
        self.tab_rail.setFixedWidth(210)
        self.tab_rail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        rail_layout = QVBoxLayout(self.tab_rail)
        rail_layout.setContentsMargins(8, 8, 8, 8)
        rail_layout.setSpacing(8)

        self.lbl_rail_header = QLabel(t("detailed_tabs_header", default="РАЗДЕЛЫ").upper(), self.tab_rail)
        self.lbl_rail_header.setObjectName("RailHeader")
        self.lbl_rail_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rail_layout.addWidget(self.lbl_rail_header)

        self.tabs: list[GlanceableTab] = []
        tab_defs = [
            (0, "🌡️", t("switch_temperature")),
            (1, "⏱️", t("switch_pressure")),
            (2, "⚡", t("switch_geomagnetic")),
            (3, "🌍", t("switch_climate_norms")),
            (4, "🧭", t("switch_wind_rose")),
        ]
        for idx, icon, title in tab_defs:
            tab = GlanceableTab(index=idx, icon_char=icon, title=title, parent=self.tab_rail)
            tab.clicked.connect(self.set_screen)
            rail_layout.addWidget(tab)
            self.tabs.append(tab)

        rail_layout.addStretch(1)
        body_layout.addWidget(self.tab_rail, 0)

        main_layout.addLayout(body_layout, 1)

        self._update_tab_rail_active(0)
        self._update_screen_badge()
        self._apply_dialog_theme()

    @property
    def pill_toggle(self) -> Any:
        class _PillShim:
            def __init__(shim_self, dlg: DetailedForecastDialogQt) -> None:
                shim_self._dlg = dlg
            def current_index(shim_self) -> int:
                return shim_self._dlg.stack.currentIndex()
            def set_index(shim_self, idx: int, notify: bool = True) -> None:
                shim_self._dlg.set_screen(idx)
            def update_labels(shim_self, labels: list[str]) -> None:
                pass
            def set_theme_light(shim_self, is_light: bool) -> None:
                pass
        return _PillShim(self)

    def next_screen(self) -> None:
        """Cycle to the next pane (▼)."""
        import time
        now = time.time()
        if now - self._last_switch_ts < 0.2:
            return
        self._last_switch_ts = now
        next_idx = (self.stack.currentIndex() + 1) % max(1, self.stack.count())
        self.set_screen(next_idx)

    def prev_screen(self) -> None:
        """Cycle to the previous pane (▲)."""
        import time
        now = time.time()
        if now - self._last_switch_ts < 0.2:
            return
        self._last_switch_ts = now
        count = max(1, self.stack.count())
        prev_idx = (self.stack.currentIndex() - 1) % count
        self.set_screen(prev_idx)

    def set_screen(self, index: int) -> None:
        """Switch stacked pane to the specified index."""
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)
            # The 24h/X-days toggle only applies to temperature, pressure and
            # geomagnetic panes; hide it on climate / wind-rose panes.
            if hasattr(self, "period_bar"):
                self.period_bar.setVisible(index in self._period_bar_panes)
            self._update_screen_badge()
            self._update_tab_rail_active(index)

    def _update_tab_rail_active(self, active_index: int) -> None:
        if hasattr(self, "tabs"):
            for idx, tab in enumerate(self.tabs):
                tab.set_active(idx == active_index)

    def keyPressEvent(self, event: Any) -> None:
        key = event.key()
        if key in (Qt.Key.Key_1, Qt.Key.Key_F1):
            self.set_screen(0)
            event.accept()
        elif key in (Qt.Key.Key_2, Qt.Key.Key_F2):
            self.set_screen(1)
            event.accept()
        elif key in (Qt.Key.Key_3, Qt.Key.Key_F3):
            self.set_screen(2)
            event.accept()
        elif key in (Qt.Key.Key_4, Qt.Key.Key_F4):
            self.set_screen(3)
            event.accept()
        elif key in (Qt.Key.Key_5, Qt.Key.Key_F5):
            self.set_screen(4)
            event.accept()
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_PageUp):
            self.prev_screen()
            event.accept()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_PageDown):
            self.next_screen()
            event.accept()
        elif key == Qt.Key.Key_Escape:
            self.accept()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _on_tab_switched(self, index: int) -> None:
        self.set_screen(index)

    def _update_screen_badge(self) -> None:
        idx = self.stack.currentIndex()
        labels = [
            t("switch_temperature"),
            t("switch_pressure"),
            t("switch_geomagnetic"),
            t("switch_climate_norms"),
            t("switch_wind_rose"),
        ]
        label = labels[idx] if 0 <= idx < len(labels) else ""
        total = max(1, self.stack.count())
        self.lbl_screen_badge.setText(f"{idx + 1}/{total} • {label}")
        self.lbl_screen_badge.setToolTip(t("switch_screen_hint"))

    def set_temp_press_period(self, period: str) -> None:
        """Switch between 24h hourly and multi-day daily views for temperature and pressure."""
        self._temp_press_period = period
        self._update_period_bar_styles()
        self._apply_temp_press_data()

    def _update_period_bar_styles(self) -> None:
        if not hasattr(self, "btn_period_24h") or not hasattr(self, "btn_period_daily"):
            return
        is_light = self._is_light_theme()
        active_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8)"
        active_color = "#ffffff"
        inactive_bg = "rgba(0, 0, 0, 0.05)" if is_light else "rgba(255, 255, 255, 0.06)"
        inactive_border = "rgba(0, 0, 0, 0.12)" if is_light else "rgba(255, 255, 255, 0.12)"
        inactive_color = "#475569" if is_light else "#94a3b8"
        hover_bg = "rgba(0, 0, 0, 0.08)" if is_light else "rgba(255, 255, 255, 0.12)"
        hover_color = "#0f172a" if is_light else "#f8fafc"

        btn_map = {
            "24h": self.btn_period_24h,
            "daily": self.btn_period_daily,
        }
        for p_key, btn in btn_map.items():
            if p_key == self._temp_press_period:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {active_bg};
                        color: {active_color};
                        font-weight: bold;
                        font-size: 12px;
                        border: none;
                        border-radius: 15px;
                        padding: 4px 20px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {inactive_bg};
                        color: {inactive_color};
                        font-weight: 500;
                        font-size: 12px;
                        border: 1px solid {inactive_border};
                        border-radius: 15px;
                        padding: 4px 20px;
                    }}
                    QPushButton:hover {{
                        background-color: {hover_bg};
                        color: {hover_color};
                    }}
                """)
        if hasattr(self, "lbl_legend_day"):
            self.lbl_legend_day.setStyleSheet(
                f"font-size: 11px; font-weight: bold; color: {'#ea580c' if is_light else '#fb923c'};"
            )
        if hasattr(self, "lbl_legend_night"):
            self.lbl_legend_night.setStyleSheet(
                f"font-size: 11px; font-weight: bold; color: {'#0284c7' if is_light else '#38bdf8'};"
            )

    def retranslate_ui(self) -> None:
        if self.config_manager:
            app_lang = self.config_manager.get("app_language", "ru")
            if app_lang == "auto" or app_lang not in ("ru", "uk", "en"):
                app_lang = "ru"
            set_language(app_lang)

        if self._data:
            from data.resources import localize_city
            app_lang = self.config_manager.get("app_language", "ru") if self.config_manager else "ru"
            loc_name, _ = localize_city(
                name=self._data.city_name,
                lat=self._data.lat,
                lon=self._data.lon,
                country=self._data.country,
                lang=app_lang,
            )
            display_title = loc_name or self._data.city_name or "—"
            self.setWindowTitle(t("detailed_title", city=display_title))
            self.lbl_city_title.setText(f"{display_title}{f', {self._data.country}' if self._data.country else ''}")
        else:
            self.setWindowTitle(t("detailed_title", city="—"))

        days_count = self._get_forecast_days_count()
        app_lang = self.config_manager.get("app_language", "ru") if self.config_manager else "ru"
        if hasattr(self, "btn_period_24h"):
            self.btn_period_24h.setText(t("forecast_tab_24h"))
        if hasattr(self, "btn_period_daily"):
            self.btn_period_daily.setText(self._format_days_tab_label(days_count, app_lang))
        if hasattr(self, "lbl_legend_day"):
            self.lbl_legend_day.setText("● " + t("forecast_legend_day"))
        if hasattr(self, "lbl_legend_night"):
            self.lbl_legend_night.setText("● " + t("forecast_legend_night"))
        if hasattr(self, "lbl_geomag_title"):
            self.lbl_geomag_title.setText(t("chart_geomagnetic_title"))

        tab_titles = [
            t("switch_temperature"),
            t("switch_pressure"),
            t("switch_geomagnetic"),
            t("switch_climate_norms"),
            t("switch_wind_rose"),
        ]
        if hasattr(self, "tabs"):
            for idx, tab in enumerate(self.tabs):
                if idx < len(tab_titles):
                    tab.update_content(title=tab_titles[idx])
        if hasattr(self, "lbl_rail_header"):
            self.lbl_rail_header.setText(t("detailed_tabs_header", default="Разделы").upper())

        self._update_screen_badge()
        self.btn_close.setToolTip(t("btn_close"))
        self.climate_widget.retranslate_ui()
        self.wind_rose_widget.retranslate_ui()
        if self._data:
            self.update_data(self._data)

    def _is_light_theme(self) -> bool:
        skin = self.config_manager.get("skin", {})
        mode = skin.get("theme_mode", "auto_solar")
        if mode == "day":
            return True
        if mode == "night":
            return False
        if mode == "auto_system":
            return is_system_light_theme()
        if mode == "auto_solar" and self._data:
            from core.astronomy import determine_solar_time_of_day
            lat = self._data.lat or 55.75
            lon = self._data.lon or 37.61
            return determine_solar_time_of_day(lat, lon)[0] == "day"
        return False

    def _apply_dialog_theme(self) -> None:
        is_light = self._is_light_theme()
        self.climate_widget.set_theme_light(is_light)
        self.wind_rose_widget.set_theme_light(is_light)
        self.spline_widget.set_theme_light(is_light)
        self.baro_widget.set_theme_light(is_light)
        self.geomag_widget.set_theme_light(is_light)
        self._update_period_bar_styles()

        if hasattr(self, "tabs"):
            for tab in self.tabs:
                tab.set_theme_light(is_light)

        bg_rail = "#f8fafc" if is_light else "#0b1220"
        border_rail = "#e2e8f0" if is_light else "rgba(255, 255, 255, 0.08)"
        rail_hdr_col = "#64748b" if is_light else "#94a3b8"

        if hasattr(self, "tab_rail"):
            self.tab_rail.setStyleSheet(f"""
                QFrame#GlanceableTabRail {{
                    background-color: {bg_rail};
                    border-left: 1px solid {border_rail};
                    border-radius: 0px 12px 12px 0px;
                }}
                QLabel#RailHeader {{
                    color: {rail_hdr_col};
                    font-size: 11px;
                    font-weight: 700;
                    letter-spacing: 1px;
                    background: transparent;
                    padding: 2px 4px;
                }}
            """)

        bg_dlg = "#ffffff" if is_light else "#0f172a"
        color_text = "#0f172a" if is_light else "#f8fafc"
        card_bg = "rgba(0, 0, 0, 0.04)" if is_light else "rgba(255, 255, 255, 0.05)"
        card_border = "rgba(0, 0, 0, 0.12)" if is_light else "rgba(255, 255, 255, 0.12)"
        badge_bg = "rgba(2, 132, 199, 0.12)" if is_light else "rgba(56, 189, 248, 0.15)"
        badge_color = "#0284c7" if is_light else "#38bdf8"
        badge_border = "rgba(2, 132, 199, 0.30)" if is_light else "rgba(56, 189, 248, 0.35)"
        badge_hover = "rgba(2, 132, 199, 0.22)" if is_light else "rgba(56, 189, 248, 0.25)"
        nav_bg = "rgba(0, 0, 0, 0.05)" if is_light else "rgba(255, 255, 255, 0.08)"
        nav_border = "rgba(0, 0, 0, 0.12)" if is_light else "rgba(255, 255, 255, 0.15)"
        nav_hover = "rgba(0, 0, 0, 0.10)" if is_light else "rgba(255, 255, 255, 0.16)"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_dlg};
                color: {color_text};
            }}
            QStackedWidget#DetailStack {{
                background-color: {bg_dlg};
            }}
            QWidget#DetailPane {{
                background-color: {bg_dlg};
            }}
            QFrame#DetailedCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 12px;
            }}
            QLabel {{
                color: {color_text};
            }}
            QLabel#ScreenBadge {{
                background-color: {badge_bg};
                color: {badge_color};
                font-size: 11px;
                font-weight: bold;
                padding: 4px 12px;
                border-radius: 12px;
                border: 1px solid {badge_border};
            }}
            QLabel#ScreenBadge:hover {{
                background-color: {badge_hover};
                border: 1px solid {badge_color};
            }}
            QPushButton#BtnPaneNav {{
                background-color: {nav_bg};
                border: 1px solid {nav_border};
                border-radius: 15px;
                color: {color_text};
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton#BtnPaneNav:hover {{
                background-color: {nav_hover};
            }}
            QPushButton#BtnPaneNav:pressed {{
                background-color: {badge_bg};
                border: 1px solid {badge_color};
            }}
            QPushButton#BtnClose {{
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 15px;
                color: {color_text};
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton#BtnClose:hover {{
                background-color: rgba(239, 68, 68, 0.85);
                color: #ffffff;
                border: none;
            }}
        """)

    def _apply_temp_press_data(self) -> None:
        """Render active period dataset (24h hourly vs X days daily) onto chart widgets."""
        if not self._data:
            return

        units_cfg = self.config_manager.get("units", {}) or {}
        t_unit = "fahrenheit" if str(units_cfg.get("temp", "C")).lower() == "f" else "celsius"
        w_unit = str(units_cfg.get("wind", "m/s"))
        p_unit = str(units_cfg.get("pressure", "mmHg"))
        lang = self.config_manager.get("weather_language", "ru")
        is_light = self._is_light_theme()

        app_lang = self.config_manager.get("app_language", "ru") if self.config_manager else "ru"
        days_count = self._get_forecast_days_count()

        if self._temp_press_period == "daily":
            actual_days = len(self._daily_points) if self._daily_points else days_count
            self.lbl_spline_title.setText(
                f"{t('chart_daily_spline_title')} ({self._format_days_tab_label(actual_days, app_lang)})"
            )
            self.lbl_baro_title.setText(
                f"{t('chart_daily_pressure_title')} ({self._format_days_tab_label(actual_days, app_lang)})"
            )
            self.lbl_legend_day.setVisible(True)
            self.lbl_legend_night.setVisible(True)

            self.spline_widget.update_daily_points(
                daily_points=self._daily_points,
                temp_unit=t_unit,
                wind_unit=w_unit,
                lang=lang,
                is_light=is_light,
            )
            self.baro_widget.update_data(
                pressures=self._press_vals_daily,
                times=self._time_labels_daily,
                press_unit=p_unit,
                lang=lang,
                is_light=is_light,
            )

            if self._press_vals_daily:
                p_min = min(self._press_vals_daily)
                p_max = max(self._press_vals_daily)
                unit_str = format_pressure(1013.25, unit=p_unit, lang=lang).split(" ", 1)[1] if " " in format_pressure(1013.25, unit=p_unit, lang=lang) else p_unit
                self.lbl_baro_curr.setText(f"{p_min:.0f} – {p_max:.0f} {unit_str}")

                p_delta = self._press_vals_daily[-1] - self._press_vals_daily[0]
                if p_delta >= 0.5:
                    self.lbl_tendency_pill.setText(f"{t('pressure_tendency_rising')} (+{p_delta:.1f})")
                    self.lbl_tendency_pill.setStyleSheet("""
                        background-color: rgba(16, 185, 129, 0.20);
                        color: #10b981;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 2px 10px;
                        border-radius: 11px;
                        border: 1px solid rgba(16, 185, 129, 0.40);
                    """)
                elif p_delta <= -0.5:
                    self.lbl_tendency_pill.setText(f"{t('pressure_tendency_falling')} ({p_delta:.1f})")
                    self.lbl_tendency_pill.setStyleSheet("""
                        background-color: rgba(245, 158, 11, 0.20);
                        color: #f59e0b;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 2px 10px;
                        border-radius: 11px;
                        border: 1px solid rgba(245, 158, 11, 0.40);
                    """)
                else:
                    self.lbl_tendency_pill.setText(t("pressure_tendency_steady"))
                    self.lbl_tendency_pill.setStyleSheet("""
                        background-color: rgba(100, 116, 139, 0.20);
                        color: #94a3b8;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 2px 10px;
                        border-radius: 11px;
                        border: 1px solid rgba(100, 116, 139, 0.40);
                    """)
        else:  # "24h"
            self.lbl_spline_title.setText(t("chart_hourly_spline_title"))
            self.lbl_baro_title.setText(t("chart_pressure_title"))
            self.lbl_legend_day.setVisible(False)
            self.lbl_legend_night.setVisible(False)

            self.spline_widget.update_points(
                points=self._points_24,
                temp_unit=t_unit,
                wind_unit=w_unit,
                lang=lang,
                is_light=is_light,
            )
            self.baro_widget.update_data(
                pressures=self._press_vals_24,
                times=self._time_labels_24,
                press_unit=p_unit,
                lang=lang,
                is_light=is_light,
            )

            cur_press_hpa = self._data.current.pressure_hpa if self._data.current else 1013.0
            self.lbl_baro_curr.setText(format_pressure(cur_press_hpa, unit=p_unit, lang=lang))

            if len(self._press_vals_24) >= 4:
                p_delta = self._press_vals_24[-1] - self._press_vals_24[0]
                if p_delta >= 0.5:
                    self.lbl_tendency_pill.setText(f"{t('pressure_tendency_rising')} (+{p_delta:.1f})")
                    self.lbl_tendency_pill.setStyleSheet("""
                        background-color: rgba(16, 185, 129, 0.20);
                        color: #10b981;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 2px 10px;
                        border-radius: 11px;
                        border: 1px solid rgba(16, 185, 129, 0.40);
                    """)
                elif p_delta <= -0.5:
                    self.lbl_tendency_pill.setText(f"{t('pressure_tendency_falling')} ({p_delta:.1f})")
                    self.lbl_tendency_pill.setStyleSheet("""
                        background-color: rgba(245, 158, 11, 0.20);
                        color: #f59e0b;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 2px 10px;
                        border-radius: 11px;
                        border: 1px solid rgba(245, 158, 11, 0.40);
                    """)
                else:
                    self.lbl_tendency_pill.setText(t("pressure_tendency_steady"))
                    self.lbl_tendency_pill.setStyleSheet("""
                        background-color: rgba(100, 116, 139, 0.20);
                        color: #94a3b8;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 2px 10px;
                        border-radius: 11px;
                        border: 1px solid rgba(100, 116, 139, 0.40);
                    """)

        self._apply_geomagnetic_data(lang=lang, is_light=is_light)

    def _apply_geomagnetic_data(self, lang: str = "ru", is_light: bool = False) -> None:
        """Render NOAA SWPC Kp-index forecast for the active period (24h vs X days)."""
        from core.geomagnetic import get_geomagnetic_forecast

        def _on_forecast_ready(forecast: Any) -> None:
            try:
                from ui.qt_compat import QTimer
                QTimer.singleShot(0, lambda: self._render_geomagnetic(forecast, lang, is_light))
            except Exception:
                pass

        forecast = get_geomagnetic_forecast(on_updated=_on_forecast_ready)
        self._render_geomagnetic(forecast, lang, is_light)

    def _render_geomagnetic(self, forecast: Any, lang: str, is_light: bool) -> None:
        """Build Kp bars (3-hour bins for 24h, daily maxima for X days) and the summary pill."""
        if not hasattr(self, "geomag_widget"):
            return

        points = getattr(forecast, "points", []) or []
        if not points:
            self.geomag_widget.update_bars([], is_light=is_light)
            self.lbl_geomag_max.setText("—")
            if hasattr(self, "tabs") and len(self.tabs) > 2:
                self.tabs[2].update_content(metric="—")
            return

        from core.geomagnetic import classify_kp_index

        # NOAA time_tags are UTC. Show the window from the current 3-hour bin
        # forward, never historical observations. Daily grouping uses local
        # calendar days so it lines up with the temperature chart.
        offset_sec = self._data.utc_offset_seconds if self._data else 0
        offset_sec = offset_sec or 0
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        cur_bin = now_utc.replace(minute=0, second=0, microsecond=0)
        cur_bin = cur_bin.replace(hour=(cur_bin.hour // 3) * 3)

        def _parse_tag(tag: str) -> datetime | None:
            try:
                return datetime.strptime(tag[:19], "%Y-%m-%dT%H:%M:%S")
            except (ValueError, TypeError):
                return None

        upcoming: list[tuple[datetime, Any]] = []
        for p in points:
            dt = _parse_tag(p.time_tag or "")
            if dt is not None and dt >= cur_bin:
                upcoming.append((dt, p))

        bars: list[dict[str, Any]] = []
        if self._temp_press_period == "daily":
            # Daily maxima grouped by local calendar day, from today forward
            by_day: dict[str, float] = {}
            for dt, p in upcoming:
                local_dt = dt + timedelta(seconds=offset_sec)
                day_key = local_dt.strftime("%Y-%m-%d")
                by_day[day_key] = max(by_day.get(day_key, 0.0), float(p.kp_index))

            for day_key in sorted(by_day.keys()):
                kp_val = by_day[day_key]
                _, status_key, color, _scale = classify_kp_index(kp_val)
                try:
                    day_dt = datetime.strptime(day_key, "%Y-%m-%d")
                    label = get_weekday_name(day_dt.weekday(), short=True, lang=lang)
                except Exception:
                    label = day_key[5:].replace("-", ".")
                bars.append({
                    "label": label,
                    "kp": kp_val,
                    "color": color,
                    "status_key": status_key,
                    "is_forecast": True,
                })
        else:
            # 24h mode: up to 8 three-hour bins starting from the current one
            for dt, p in upcoming[:8]:
                kp_val = float(p.kp_index)
                _, status_key, color, _scale = classify_kp_index(kp_val)
                local_dt = dt + timedelta(seconds=offset_sec)
                bars.append({
                    "label": local_dt.strftime("%H:%M"),
                    "kp": kp_val,
                    "color": color,
                    "status_key": status_key,
                    "is_forecast": p.is_forecast,
                })

        self.geomag_widget.update_bars(bars, is_light=is_light)

        # Summary pill: peak Kp over the shown window with its classification
        peak_kp = max((b["kp"] for b in bars), default=0.0)
        _level, status_key, color, noaa_scale = classify_kp_index(peak_kp)
        status_desc = t(status_key, _lang=lang)
        self.lbl_geomag_max.setText(f"{t('chart_geomagnetic_peak', _lang=lang)}: {peak_kp:.1f} ({status_desc})")
        self.lbl_geomag_max.setStyleSheet(f"""
            background-color: rgba(100, 116, 139, 0.20);
            color: {color};
            font-weight: bold;
            font-size: 11px;
            padding: 2px 10px;
            border-radius: 11px;
            border: 1px solid rgba(100, 116, 139, 0.40);
        """)
        self.lbl_geomag_max.setToolTip(
            f"{t('chart_geomagnetic_title', _lang=lang)} — {status_desc} ({noaa_scale}, Kp {peak_kp:.1f})"
        )
        if hasattr(self, "tabs") and len(self.tabs) > 2:
            self.tabs[2].update_content(metric=f"Kp {peak_kp:.1f} ({status_desc})")

    def update_data(self, data: WeatherForecastData) -> None:
        self._data = data
        self.setWindowTitle(t("detailed_title", city=data.city_name or "—"))
        self.lbl_city_title.setText(f"{data.city_name}{f', {data.country}' if data.country else ''}")

        units_cfg = self.config_manager.get("units", {}) or {}
        p_unit = str(units_cfg.get("pressure", "mmHg"))
        lang = self.config_manager.get("weather_language", "ru")
        is_light = self._is_light_theme()

        # 1. Prepare 24 points starting from current local hour forward (now to now+24h)
        points_24: list[dict[str, Any]] = []

        utc_now = datetime.now(timezone.utc)
        offset_sec = data.utc_offset_seconds if data.utc_offset_seconds is not None else 0
        local_now = datetime.fromtimestamp(utc_now.timestamp() + offset_sec, timezone.utc)
        cur_hour = local_now.hour
        cur_hour_iso = local_now.strftime("%Y-%m-%dT%H:00")

        if data.hourly and len(data.hourly) >= 24:
            # Locate current hour index in data.hourly
            start_idx = -1
            for idx, h in enumerate(data.hourly):
                h_iso = getattr(h, "time_iso", "") or ""
                if h_iso and h_iso >= cur_hour_iso[:13]:
                    start_idx = idx
                    break
            if start_idx == -1:
                for idx, h in enumerate(data.hourly):
                    h_time = getattr(h, "time", "") or ""
                    h_hour = getattr(h, "hour_num", None)
                    if h_hour == cur_hour or h_time.startswith(f"{cur_hour:02d}:"):
                        start_idx = idx
                        break
            if start_idx == -1:
                start_idx = 0

            # Gather 24 consecutive points starting from current hour
            if start_idx + 24 <= len(data.hourly):
                selected_hourly = data.hourly[start_idx : start_idx + 24]
            else:
                selected_hourly = []
                for i in range(24):
                    selected_hourly.append(data.hourly[(start_idx + i) % len(data.hourly)])

            points_24 = [
                {
                    "time": (h.time if (start_idx + i < len(data.hourly) and h.time) else f"{(cur_hour + i) % 24:02d}:00"),
                    "temp": h.temp,
                    "code": h.code,
                    "is_day": h.is_day,
                    "wind_speed": h.wind_speed,
                    "wind_direction": h.wind_direction,
                    "precip_prob": h.precip_prob,
                    "pressure_hpa": h.pressure_hpa,
                }
                for i, h in enumerate(selected_hourly)
            ]
        elif data.days_detailed and len(data.days_detailed) > 0:
            for i in range(24):
                h = (cur_hour + i) % 24
                d_idx = (cur_hour + i) // 24
                d_src = data.days_detailed[d_idx] if d_idx < len(data.days_detailed) else data.days_detailed[0]

                val_t = d_src.hourly_temps[h] if len(d_src.hourly_temps) > h else 15.0
                val_c = d_src.hourly_codes[h] if len(d_src.hourly_codes) > h else 0
                val_d = d_src.hourly_is_days[h] if len(d_src.hourly_is_days) > h else 1
                val_w = d_src.hourly_winds[h] if len(d_src.hourly_winds) > h else 3.0
                val_dir = d_src.hourly_wind_dirs[h] if len(d_src.hourly_wind_dirs) > h else 240
                val_p = d_src.hourly_probs[h] if len(d_src.hourly_probs) > h else 0
                val_press = d_src.hourly_press_hpa[h] if len(d_src.hourly_press_hpa) > h else 1013.0

                points_24.append({
                    "time": f"{h:02d}:00",
                    "temp": val_t,
                    "code": val_c,
                    "is_day": val_d,
                    "wind_speed": val_w,
                    "wind_direction": val_dir,
                    "precip_prob": val_p,
                    "pressure_hpa": val_press,
                })
        elif data.hourly and len(data.hourly) > 0:
            for i in range(24):
                h_item = data.hourly[i % len(data.hourly)]
                points_24.append({
                    "time": f"{(cur_hour + i) % 24:02d}:00",
                    "temp": h_item.temp,
                    "code": h_item.code,
                    "is_day": h_item.is_day,
                    "wind_speed": h_item.wind_speed,
                    "wind_direction": h_item.wind_direction,
                    "precip_prob": h_item.precip_prob,
                    "pressure_hpa": h_item.pressure_hpa,
                })

        self._points_24 = points_24
        press_hpa_list = [p.get("pressure_hpa", 1013.0) for p in points_24]
        self._press_vals_24 = [
            float(convert_pressure(h, unit=p_unit) or 0.0)
            for h in press_hpa_list
        ]
        self._time_labels_24 = [p.get("time", "") for p in points_24]

        # 2. Prepare multi-day forecast points for configured days count
        days_count = self._get_forecast_days_count()
        daily_source = data.daily[:days_count] if data.daily else []
        if not daily_source and data.days_detailed:
            daily_source = data.days_detailed[:days_count]

        daily_points: list[dict[str, Any]] = []
        press_vals_daily: list[float] = []
        time_labels_daily: list[str] = []

        for idx, d in enumerate(daily_source):
            w_idx = getattr(d, "weekday_idx", None)
            if w_idx is not None:
                day_name = get_weekday_name(w_idx, short=True, lang=lang)
                day_full = get_weekday_name(w_idx, short=False, lang=lang)
            else:
                day_name = getattr(d, "day", f"+{idx+1}")
                day_full = day_name

            date_str = getattr(d, "date_str", "")
            code = getattr(d, "code", 0)
            day_t = getattr(d, "max", getattr(d, "t_max", 0.0))
            night_t = getattr(d, "min", getattr(d, "t_min", 0.0))
            precip_prob = getattr(d, "precip_prob_max", 0)

            wind_spd = 0.0
            wind_dir = 0
            d_det = data.days_detailed[idx] if (data.days_detailed and idx < len(data.days_detailed)) else None
            if d_det:
                wind_spd = getattr(d_det, "wind_max", 0.0)
                wind_dir = getattr(d_det, "dominant_wind_dir", 0)

            daily_points.append({
                "day": day_name,
                "day_full": day_full,
                "date": date_str,
                "day_temp": day_t,
                "night_temp": night_t,
                "code": code,
                "wind_speed": wind_spd,
                "wind_direction": wind_dir,
                "precip_prob": precip_prob,
            })

            # Calculate representative daily pressure
            p_hpa = None
            if d_det:
                if d_det.hourly_press_hpa and len(d_det.hourly_press_hpa) > 0:
                    p_hpa = sum(d_det.hourly_press_hpa) / len(d_det.hourly_press_hpa)
                elif d_det.min_pressure_mm and d_det.max_pressure_mm:
                    p_hpa = ((d_det.min_pressure_mm + d_det.max_pressure_mm) / 2.0) * 1.33322
            if p_hpa is None:
                if data.hourly and (idx * 24 + 12 < len(data.hourly)):
                    p_hpa = getattr(data.hourly[idx * 24 + 12], "pressure_hpa", 1013.0)
                elif data.current and data.current.pressure_hpa:
                    p_hpa = data.current.pressure_hpa
                else:
                    p_hpa = 1013.0

            press_vals_daily.append(float(convert_pressure(p_hpa, unit=p_unit) or 0.0))
            time_labels_daily.append(day_name)

        self._daily_points = daily_points
        self._press_vals_daily = press_vals_daily
        self._time_labels_daily = time_labels_daily

        # Update glanceable metric on Tab 0 (Temperature)
        t_curr = data.current.temp if data.current else None
        if t_curr is not None:
            t_unit_cfg = str(units_cfg.get("temp", "C")).upper()
            t_sym = f"°{t_unit_cfg}" if t_unit_cfg in ("C", "F") else "°C"
            if self._daily_points:
                d0 = self._daily_points[0]
                d_max = d0.get("day_temp", 0.0)
                d_min = d0.get("night_temp", 0.0)
                t_metric = f"{t_curr:+0.0f}{t_sym} ({d_min:+0.0f}°..{d_max:+0.0f}°)"
            else:
                t_metric = f"{t_curr:+0.0f}{t_sym}"
        else:
            t_metric = "—"
        if hasattr(self, "tabs") and len(self.tabs) > 0:
            self.tabs[0].update_content(metric=t_metric)

        # Update glanceable metric on Tab 1 (Pressure)
        if self._press_vals_24:
            p_val = self._press_vals_24[0]
            p_delta = self._press_vals_24[-1] - self._press_vals_24[0]
            trend_arrow = "↗" if p_delta >= 0.5 else ("↘" if p_delta <= -0.5 else "→")
            p_unit_short = "мм" if "mm" in p_unit.lower() else ("hPa" if "hpa" in p_unit.lower() else p_unit)
            p_metric = f"{p_val:.0f} {p_unit_short} {trend_arrow}"
        elif self._press_vals_daily:
            p_val = self._press_vals_daily[0]
            p_unit_short = "мм" if "mm" in p_unit.lower() else ("hPa" if "hpa" in p_unit.lower() else p_unit)
            p_metric = f"{p_val:.0f} {p_unit_short}"
        else:
            p_metric = "—"
        if hasattr(self, "tabs") and len(self.tabs) > 1:
            self.tabs[1].update_content(metric=p_metric)

        # 3. Apply active period view (also updates geomagnetic view & Tab 2)
        self._apply_temp_press_data()

        if data.current:
            c_text = data.current.condition_text or ""
            t_str = f"{data.current.temp:+0.0f}°C"
            self.lbl_cond_summary.setText(f"•   {t_str}   {c_text}")

        # 4. Climate Normals (ERA5) & Tab 3
        self.climate_widget.update_climate_data(data, lang=lang, is_light=is_light)
        anom_txt = self.climate_widget.lbl_anom_val.text().strip()
        if anom_txt:
            anom_lbl = t("climate_norm_anomaly", _lang=lang)
            if anom_lbl == "climate_norm_anomaly":
                anom_lbl = "к норме"
            clim_metric = f"{anom_txt} {anom_lbl}"
        else:
            clim_metric = "—"
        if hasattr(self, "tabs") and len(self.tabs) > 3:
            self.tabs[3].update_content(metric=clim_metric)

        # 5. 16-ray Stacked Wind Rose & Tab 4
        self.wind_rose_widget.update_wind_data(data, is_light=is_light, lang=lang)
        if data.current:
            w_spd = getattr(data.current, "wind_speed", 0.0) or 0.0
            w_dir = getattr(data.current, "wind_direction", 0) or 0
            w_unit = str(units_cfg.get("wind", "m/s"))
            cardinal = cardinal_from_degrees(w_dir, lang=lang)
            wind_metric = f"{w_spd:.1f} {w_unit} ({cardinal})"
        else:
            wind_metric = "—"
        if hasattr(self, "tabs") and len(self.tabs) > 4:
            self.tabs[4].update_content(metric=wind_metric)

        # Data may raise pane minimums; keep the static size in sync (grow-only).
        self._fit_static_size()


DetailedForecastDialog = DetailedForecastDialogQt
