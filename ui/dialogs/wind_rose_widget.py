"""16-Ray Stacked Wind Rose Widget for Detailed Forecast Dialog in PySide6 / Qt6.

Implements:
1. 16-ray stacked wind rose (speed bands: <2, 2-4, 4-6, 6-8, 8-11, >11 m/s).
2. Period selector buttons: 1 hour, 8 hours, Day/Night (dynamic), 24 hours.
3. 4 Corner Info cards: Wind Gust, Direction (deg + cardinal), Beaufort Scale, Prevailing Sector.
4. Concentric percentage circles and 16 cardinal labels.
5. Calm center hub with percentage.
6. Bottom horizontal speed distribution bar with current speed marker.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from core.astronomy import determine_solar_time_of_day
from core.i18n import t
from core.units import (
    cardinal_from_degrees,
    format_wind_speed,
    get_beaufort_name,
    get_beaufort_number,
)
from data.wmo_conditions import WIND_DIRECTIONS_16
from models.weather import WeatherForecastData
from ui.qt_compat import (
    QColor,
    QFont,
    QFrame,
    QHBoxLayout,
    QPainter,
    QPen,
    QPointF,
    QPolygonF,
    QPushButton,
    QRectF,
    QSizePolicy,
    Qt,
    QtCore,
    QVBoxLayout,
    QWidget,
)

# 6 Speed Classes & Colors (as agreed upon and approved)
SPEED_BINS = [
    (0.5, 2.0),
    (2.0, 4.0),
    (4.0, 6.0),
    (6.0, 8.0),
    (8.0, 11.0),
    (11.0, 999.0),
]

BIN_COLORS = [
    QColor("#3b82f6"),  # < 2 m/s: Vibrant Blue
    QColor("#06b6d4"),  # 2 - 4 m/s: Cyan
    QColor("#10b981"),  # 4 - 6 m/s: Emerald Green
    QColor("#eab308"),  # 6 - 8 m/s: Yellow
    QColor("#f97316"),  # 8 - 11 m/s: Orange
    QColor("#ef4444"),  # > 11 m/s: Red
]

BIN_HEX_COLORS = ["#3b82f6", "#06b6d4", "#10b981", "#eab308", "#f97316", "#ef4444"]
BIN_LABELS = ["<2", "2-4", "4-6", "6-8", "8-11", ">11"]


class WindRoseCanvas(QWidget):
    """QPainter canvas rendering the 16-ray stacked wind rose, corner cards, and bottom bars."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 430)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._is_light: bool = False
        self._lang: str = "ru"
        self._wind_unit: str = "m/s"

        # Wind calculation data
        self._sector_bins: list[list[float]] = [[0.0] * 6 for _ in range(16)]
        self._sector_totals: list[float] = [0.0] * 16
        self._calm_pct: float = 0.0
        self._max_pct: float = 25.0
        self._speed_dist: list[float] = [0.0] * 6

        # Corner values
        self._gust_speed: float = 0.0
        self._curr_speed: float = 0.0
        self._curr_dir: float = 0.0
        self._prevailing_sector: int = 0
        self._prevailing_pct: float = 0.0

    def set_theme_light(self, is_light: bool) -> None:
        self._is_light = is_light
        self.update()

    def set_data(
        self,
        sector_bins: list[list[float]],
        sector_totals: list[float],
        calm_pct: float,
        speed_dist: list[float],
        gust_speed: float,
        curr_speed: float,
        curr_dir: float,
        prevailing_sector: int,
        prevailing_pct: float,
        lang: str = "ru",
        wind_unit: str = "m/s",
    ) -> None:
        self._sector_bins = sector_bins
        self._sector_totals = sector_totals
        self._calm_pct = calm_pct
        self._speed_dist = speed_dist
        self._gust_speed = gust_speed
        self._curr_speed = curr_speed
        self._curr_dir = curr_dir
        self._prevailing_sector = prevailing_sector
        self._prevailing_pct = prevailing_pct
        self._lang = lang
        self._wind_unit = wind_unit

        max_sec = max(sector_totals) if sector_totals else 0.0
        # Determine scale ceiling (e.g. 15%, 25%, 35%, 50%, etc.)
        if max_sec <= 15.0:
            self._max_pct = 15.0
        elif max_sec <= 25.0:
            self._max_pct = 25.0
        elif max_sec <= 40.0:
            self._max_pct = 40.0
        else:
            self._max_pct = math.ceil(max_sec / 10.0) * 10.0

        self.update()

    @staticmethod
    def _polar(cx: float, cy: float, radius: float, degrees: float) -> QPointF:
        """Polar to Cartesian with 0° at North (12 o'clock), clockwise."""
        rad = math.radians(degrees)
        return QPointF(cx + radius * math.sin(rad), cy - radius * math.cos(rad))

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self.width())
        h = float(self.height())
        is_light = self._is_light

        # Background palette
        col_text = QColor("#0f172a") if is_light else QColor("#f8fafc")
        col_muted = QColor("#64748b") if is_light else QColor("#94a3b8")
        col_card_bg = QColor(0, 0, 0, 10) if is_light else QColor(255, 255, 255, 12)
        col_card_border = QColor(0, 0, 0, 25) if is_light else QColor(255, 255, 255, 20)
        col_ring = QColor(0, 0, 0, 20) if is_light else QColor(255, 255, 255, 30)
        col_spoke = QColor(0, 0, 0, 12) if is_light else QColor(255, 255, 255, 18)

        # ---------------------------------------------------------------------
        # 1. Four Corner Info Cards
        # ---------------------------------------------------------------------
        card_w = min(150.0, max(120.0, w * 0.26))
        card_h = 50.0
        margin_x = 14.0
        top_y = 10.0
        bottom_y = h - 68.0

        # Data for cards
        gust_str = format_wind_speed(self._gust_speed, self._wind_unit, lang=self._lang)
        dir_cardinal = cardinal_from_degrees(self._curr_dir, lang=self._lang)
        dir_str = f"{int(round(self._curr_dir))}° {dir_cardinal}"

        b_num = get_beaufort_number(self._curr_speed)
        b_name = get_beaufort_name(self._curr_speed, lang=self._lang)
        bft_str = f"{b_num} {t('unit_beaufort', _lang=self._lang)} • {b_name}"

        dirs_16 = WIND_DIRECTIONS_16.get(self._lang, WIND_DIRECTIONS_16["ru"])
        prev_cardinal = dirs_16[self._prevailing_sector % 16] if dirs_16 else "—"
        prev_str = f"{prev_cardinal} • {self._prevailing_pct:.0f}%"

        corners = [
            # Top-Left: Wind Gust
            (margin_x, top_y, t("wind_gust_title", _lang=self._lang), gust_str, "#f97316"),
            # Top-Right: Direction
            (w - card_w - margin_x, top_y, t("wind_direction_title", _lang=self._lang), dir_str, "#38bdf8" if not is_light else "#0284c7"),
            # Bottom-Left: Beaufort
            (margin_x, bottom_y, t("wind_beaufort_title", _lang=self._lang), bft_str, col_text.name()),
            # Bottom-Right: Prevailing
            (w - card_w - margin_x, bottom_y, t("wind_prevailing_title", _lang=self._lang), prev_str, "#38bdf8" if not is_light else "#0284c7"),
        ]

        for cx_card, cy_card, title, val, val_col in corners:
            card_rect = QRectF(cx_card, cy_card, card_w, card_h)
            painter.setPen(QPen(col_card_border, 1.0))
            painter.setBrush(col_card_bg)
            painter.drawRoundedRect(card_rect, 10.0, 10.0)

            # Title
            painter.setFont(QFont(self.font().family() or "sans-serif", 9, QFont.Weight.Medium))
            painter.setPen(col_muted)
            painter.drawText(
                QRectF(cx_card + 10, cy_card + 6, card_w - 20, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )

            # Value
            font_sz = 12 if len(val) > 14 else 14
            painter.setFont(QFont(self.font().family() or "sans-serif", font_sz, QFont.Weight.Bold))
            painter.setPen(QColor(val_col))
            painter.drawText(
                QRectF(cx_card + 10, cy_card + 22, card_w - 20, 24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                val,
            )

        # ---------------------------------------------------------------------
        # 2. Circular Wind Rose Geometry
        # ---------------------------------------------------------------------
        center_x = w / 2.0
        center_y = (top_y + card_h + bottom_y) / 2.0 - 2.0
        avail_r = min((w - card_w * 2.0) / 2.0 + 30.0, (bottom_y - (top_y + card_h)) / 2.0 + 10.0)
        r_max = max(90.0, min(140.0, avail_r))

        r_calm = r_max * 0.22
        r_band_max = r_max * 0.88
        r_label = r_max * 1.06

        # Radial spokes (16 axes)
        painter.setPen(QPen(col_spoke, 1.0, Qt.PenStyle.DashLine))
        for i in range(16):
            deg = i * 22.5
            p_start = self._polar(center_x, center_y, r_calm, deg)
            p_end = self._polar(center_x, center_y, r_band_max, deg)
            painter.drawLine(p_start, p_end)

        # Concentric percentage circles
        num_rings = 3
        painter.setFont(QFont(self.font().family() or "sans-serif", 8))
        for ring_idx in range(1, num_rings + 1):
            fraction = ring_idx / num_rings
            ring_r = r_calm + fraction * (r_band_max - r_calm)
            pct_val = fraction * self._max_pct

            painter.setPen(QPen(col_ring, 1.0, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(center_x, center_y), ring_r, ring_r)

            # Percentage label on 45° (NE) axis
            lbl_pt = self._polar(center_x, center_y, ring_r, 45.0)
            painter.setPen(col_muted)
            painter.drawText(
                QRectF(lbl_pt.x() + 2, lbl_pt.y() - 12, 34, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{pct_val:.0f}%",
            )

        # ---------------------------------------------------------------------
        # 3. 16 Stacked Rays (Annular Wedges)
        # ---------------------------------------------------------------------
        ray_angular_width = 18.5  # 18.5° out of 22.5° sector leaves crisp 4.0° gap
        half_width = ray_angular_width / 2.0

        for s in range(16):
            sector_center_deg = s * 22.5
            deg_start = sector_center_deg - half_width
            deg_end = sector_center_deg + half_width

            cum_pct = 0.0
            for b in range(6):
                val_pct = self._sector_bins[s][b]
                if val_pct <= 0.001:
                    continue

                r_inner = r_calm + (cum_pct / self._max_pct) * (r_band_max - r_calm)
                r_outer = r_calm + ((cum_pct + val_pct) / self._max_pct) * (r_band_max - r_calm)
                r_outer = min(r_outer, r_band_max)
                cum_pct += val_pct

                # Build polygon along arcs using steps
                steps = 5
                pts: list[QPointF] = []
                for step_i in range(steps + 1):
                    a = deg_start + (deg_end - deg_start) * (step_i / steps)
                    pts.append(self._polar(center_x, center_y, r_inner, a))
                for step_i in range(steps, -1, -1):
                    a = deg_start + (deg_end - deg_start) * (step_i / steps)
                    pts.append(self._polar(center_x, center_y, r_outer, a))

                poly = QPolygonF(pts)
                painter.setPen(QPen(QColor(0, 0, 0, 70) if not is_light else QColor(255, 255, 255, 80), 0.75))
                painter.setBrush(BIN_COLORS[b])
                painter.drawPolygon(poly)

        # ---------------------------------------------------------------------
        # 4. 16 Cardinal Direction Labels
        # ---------------------------------------------------------------------
        for s in range(16):
            deg = s * 22.5
            label = dirs_16[s] if s < len(dirs_16) else ""
            pt = self._polar(center_x, center_y, r_label, deg)

            # Styling hierarchy: 4 main cardinals > 4 ordinals > 8 secondary
            if s % 4 == 0:  # N, E, S, W
                painter.setFont(QFont(self.font().family() or "sans-serif", 11, QFont.Weight.Bold))
                painter.setPen(QColor("#38bdf8") if s == 0 else col_text)
            elif s % 2 == 0:  # NE, SE, SW, NW
                painter.setFont(QFont(self.font().family() or "sans-serif", 9, QFont.Weight.DemiBold))
                painter.setPen(col_text)
            else:  # Secondary 8
                painter.setFont(QFont(self.font().family() or "sans-serif", 8, QFont.Weight.Normal))
                painter.setPen(col_muted)

            lbl_w, lbl_h = 36.0, 18.0
            painter.drawText(
                QRectF(pt.x() - lbl_w / 2.0, pt.y() - lbl_h / 2.0, lbl_w, lbl_h),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

        # ---------------------------------------------------------------------
        # 5. Center Calm Circle
        # ---------------------------------------------------------------------
        painter.setPen(QPen(col_card_border, 1.5))
        painter.setBrush(QColor("#0f172a") if not is_light else QColor("#ffffff"))
        painter.drawEllipse(QPointF(center_x, center_y), r_calm, r_calm)

        painter.setFont(QFont(self.font().family() or "sans-serif", 8, QFont.Weight.Medium))
        painter.setPen(col_muted)
        painter.drawText(
            QRectF(center_x - r_calm, center_y - r_calm * 0.70, r_calm * 2.0, r_calm * 0.75),
            Qt.AlignmentFlag.AlignCenter,
            t("wind_calm_label", _lang=self._lang),
        )

        painter.setFont(QFont(self.font().family() or "sans-serif", 10, QFont.Weight.Bold))
        painter.setPen(col_text)
        painter.drawText(
            QRectF(center_x - r_calm, center_y - 2, r_calm * 2.0, r_calm * 0.85),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._calm_pct:.0f}%",
        )

        # ---------------------------------------------------------------------
        # 6. Current Wind Direction Pointer (Weather Vane Needle)
        # ---------------------------------------------------------------------
        painter.save()
        painter.translate(center_x, center_y)
        # Pointer needle points to current wind direction (where wind comes from)
        wind_angle = self._curr_dir % 360.0
        painter.rotate(wind_angle)

        needle_len = r_band_max * 0.95
        needle_w = max(4.0, r_max * 0.05)

        # Pointer arrow polygon
        painter.setPen(QPen(QColor("#ffffff" if not is_light else "#0f172a"), 1.0))
        painter.setBrush(QColor("#ef4444"))
        arrow_poly = QPolygonF([
            QPointF(0.0, -needle_len),
            QPointF(needle_w, -r_calm * 1.1),
            QPointF(-needle_w, -r_calm * 1.1),
        ])
        painter.drawPolygon(arrow_poly)
        painter.restore()

        # ---------------------------------------------------------------------
        # 7. Bottom Horizontal Speed Distribution Bar
        # ---------------------------------------------------------------------
        bar_x = 24.0
        bar_y = h - 22.0
        bar_w = w - 48.0
        bar_h = 10.0

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 15) if not is_light else QColor(0, 0, 0, 15))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 5.0, 5.0)

        # Stacked distribution segments
        tot_dist = sum(self._speed_dist)
        if tot_dist > 0.0:
            cur_x = bar_x
            for b in range(6):
                seg_w = bar_w * (self._speed_dist[b] / tot_dist)
                if seg_w > 0.5:
                    painter.setBrush(BIN_COLORS[b])
                    painter.drawRect(QRectF(cur_x, bar_y, seg_w, bar_h))
                    cur_x += seg_w

        # Speed legend ticks & labels
        painter.setFont(QFont(self.font().family() or "sans-serif", 8))
        step_w = bar_w / 6.0
        for b in range(6):
            lbl_x = bar_x + b * step_w
            lbl_rect = QRectF(lbl_x, bar_y - 14, step_w, 12)
            painter.setPen(col_muted)
            painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, BIN_LABELS[b])

        # Current wind speed marker (▼ pointer above bar)
        curr_spd = self._curr_speed
        # Map current speed to bar_x..bar_x+bar_w
        # 0..12 m/s maps across bar_w
        spd_clamped = max(0.0, min(12.0, curr_spd))
        marker_x = bar_x + bar_w * (spd_clamped / 12.0)
        marker_x = max(bar_x + 4.0, min(bar_x + bar_w - 4.0, marker_x))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f87171"))
        marker_poly = QPolygonF([
            QPointF(marker_x, bar_y - 1.0),
            QPointF(marker_x - 4.0, bar_y - 6.0),
            QPointF(marker_x + 4.0, bar_y - 6.0),
        ])
        painter.drawPolygon(marker_poly)


class FullWindRoseWidget(QFrame):
    """Container widget providing period buttons, canvas, and data processing."""

    def __init__(self, parent: QWidget | None = None, config_manager: Any = None) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self._data: WeatherForecastData | None = None
        self._is_light: bool = False
        self._lang: str = "ru"
        self._current_period: str = "8h"  # Default to 8 hours

        self.setObjectName("FullWindRoseWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # 1. Top Period Selector Buttons
        self.period_bar = QFrame(self)
        self.period_bar.setObjectName("WindPeriodBar")
        p_layout = QHBoxLayout(self.period_bar)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(6)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.buttons: dict[str, QPushButton] = {}
        for key in ("1h", "8h", "day_night", "24h"):
            btn = QPushButton(key, self.period_bar)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _, p=key: self.set_period(p))
            p_layout.addWidget(btn)
            self.buttons[key] = btn

        layout.addWidget(self.period_bar)

        # 2. Wind Rose Canvas
        self.canvas = WindRoseCanvas(self)
        layout.addWidget(self.canvas, 1)

        self._update_styles()

    def is_interactive_control(self, obj: QtCore.QObject) -> bool:
        """Returns True if the object is one of the period selector buttons or bar."""
        if obj == self.period_bar:
            return True
        for btn in self.buttons.values():
            if obj == btn or btn.isAncestorOf(obj):
                return True
        return False

    def set_theme_light(self, is_light: bool) -> None:
        self._is_light = is_light
        self.canvas.set_theme_light(is_light)
        self._update_styles()

    def set_period(self, period: str) -> None:
        self._current_period = period
        self._update_styles()
        if self._data:
            self._recalculate()

    def update_wind_data(
        self,
        data: WeatherForecastData,
        is_light: bool = False,
        lang: str = "ru",
    ) -> None:
        self._data = data
        self._is_light = is_light
        self._lang = lang
        self.canvas.set_theme_light(is_light)
        self.retranslate_ui()
        self._recalculate()

    def retranslate_ui(self) -> None:
        # Determine day vs night for dynamic button text
        is_day_now = True
        if self._data and self._data.current:
            is_day_now = bool(self._data.current.is_day)
        elif self._data and self._data.lat and self._data.lon:
            s_time = determine_solar_time_of_day(
                self._data.lat,
                self._data.lon,
                utc_offset_hours=(self._data.utc_offset_seconds or 0) / 3600.0,
            )
            is_day_now = (s_time[0] == "day")

        day_night_key = "wind_period_day" if is_day_now else "wind_period_night"

        self.buttons["1h"].setText(t("wind_period_1h", _lang=self._lang))
        self.buttons["8h"].setText(t("wind_period_8h", _lang=self._lang))
        self.buttons["day_night"].setText(t(day_night_key, _lang=self._lang))
        self.buttons["24h"].setText(t("wind_period_24h", _lang=self._lang))

    def _update_styles(self) -> None:
        is_light = self._is_light
        active_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8)"
        active_color = "#ffffff"
        inactive_bg = "rgba(0, 0, 0, 0.05)" if is_light else "rgba(255, 255, 255, 0.06)"
        inactive_border = "rgba(0, 0, 0, 0.12)" if is_light else "rgba(255, 255, 255, 0.12)"
        inactive_color = "#475569" if is_light else "#94a3b8"
        hover_bg = "rgba(0, 0, 0, 0.08)" if is_light else "rgba(255, 255, 255, 0.12)"
        hover_color = "#0f172a" if is_light else "#f8fafc"

        for p_key, btn in self.buttons.items():
            if p_key == self._current_period:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {active_bg};
                        color: {active_color};
                        font-weight: bold;
                        font-size: 12px;
                        border: none;
                        border-radius: 15px;
                        padding: 4px 16px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {inactive_bg};
                        color: {inactive_color};
                        font-weight: 600;
                        font-size: 12px;
                        border: 1px solid {inactive_border};
                        border-radius: 15px;
                        padding: 4px 16px;
                    }}
                    QPushButton:hover {{
                        background: {hover_bg};
                        color: {hover_color};
                    }}
                """)

    def _recalculate(self) -> None:
        if not self._data:
            return

        data = self._data
        cur = data.current
        curr_speed = cur.wind_speed if cur else 0.0
        curr_dir = float(cur.wind_direction) if cur else 0.0
        gust_speed = cur.wind_gusts if (cur and cur.wind_gusts is not None) else curr_speed * 1.35

        # Slicing samples according to selected period
        utc_now = datetime.now(timezone.utc)
        offset_sec = data.utc_offset_seconds if data.utc_offset_seconds is not None else 0
        local_now = datetime.fromtimestamp(utc_now.timestamp() + offset_sec, timezone.utc)
        cur_hour = local_now.hour
        cur_hour_iso = local_now.strftime("%Y-%m-%dT%H:00")

        # Extract consecutive hourly records starting from current hour
        samples: list[dict[str, Any]] = []

        if data.hourly and len(data.hourly) > 0:
            start_idx = -1
            for idx, h in enumerate(data.hourly):
                h_iso = getattr(h, "time_iso", "") or ""
                if h_iso and h_iso >= cur_hour_iso[:13]:
                    start_idx = idx
                    break
            if start_idx == -1:
                for idx, h in enumerate(data.hourly):
                    h_hour = getattr(h, "hour_num", None)
                    if h_hour == cur_hour:
                        start_idx = idx
                        break
            if start_idx == -1:
                start_idx = 0

            for i in range(24):
                h_item = data.hourly[(start_idx + i) % len(data.hourly)]
                samples.append({
                    "wind_speed": h_item.wind_speed,
                    "wind_direction": h_item.wind_direction,
                    "wind_gusts": getattr(h_item, "wind_gusts", None),
                    "is_day": h_item.is_day,
                })
        elif data.days_detailed and len(data.days_detailed) > 0:
            for i in range(24):
                h = (cur_hour + i) % 24
                d_idx = (cur_hour + i) // 24
                d_src = data.days_detailed[d_idx] if d_idx < len(data.days_detailed) else data.days_detailed[0]
                val_w = d_src.hourly_winds[h] if len(d_src.hourly_winds) > h else curr_speed
                val_dir = d_src.hourly_wind_dirs[h] if len(d_src.hourly_wind_dirs) > h else curr_dir
                val_d = d_src.hourly_is_days[h] if len(d_src.hourly_is_days) > h else 1
                samples.append({
                    "wind_speed": val_w,
                    "wind_direction": val_dir,
                    "wind_gusts": val_w * 1.35,
                    "is_day": val_d,
                })
        else:
            # Fallback to single current sample
            samples.append({
                "wind_speed": curr_speed,
                "wind_direction": curr_dir,
                "wind_gusts": gust_speed,
                "is_day": cur.is_day if cur else 1,
            })

        # Filter according to period
        filtered: list[dict[str, Any]] = []
        if self._current_period == "1h":
            filtered = samples[:1]
        elif self._current_period == "8h":
            filtered = samples[:8]
        elif self._current_period == "day_night":
            is_day_now = bool(cur.is_day) if cur else True
            target_is_day = 1 if is_day_now else 0
            filtered = [s for s in samples if s.get("is_day") == target_is_day]
            if not filtered:
                filtered = samples[:12]
        else:  # "24h"
            filtered = samples[:24]

        if not filtered:
            filtered = samples[:1]

        # Max gust in selected period
        max_period_gust = gust_speed
        for s in filtered:
            g = s.get("wind_gusts")
            if g is not None and g > max_period_gust:
                max_period_gust = g

        # Aggregate counts into 16 sectors and 6 speed bins
        sector_counts: list[list[int]] = [[0] * 6 for _ in range(16)]
        speed_dist_counts: list[int] = [0] * 6
        calm_count = 0
        total_samples = len(filtered)

        for s in filtered:
            spd = float(s.get("wind_speed", 0.0) or 0.0)
            deg = float(s.get("wind_direction", 0.0) or 0.0)

            if spd < 0.5:
                calm_count += 1
                continue

            # Classify speed bin
            bin_idx = 0
            if spd < 2.0:
                bin_idx = 0
            elif spd < 4.0:
                bin_idx = 1
            elif spd < 6.0:
                bin_idx = 2
            elif spd < 8.0:
                bin_idx = 3
            elif spd < 11.0:
                bin_idx = 4
            else:
                bin_idx = 5

            speed_dist_counts[bin_idx] += 1

            # Sector index (0..15): 0=N, 1=NNE, etc.
            sector_idx = int(((deg % 360.0) + 11.25) / 22.5) % 16
            sector_counts[sector_idx][bin_idx] += 1

        calm_pct = (calm_count / total_samples) * 100.0 if total_samples > 0 else 0.0

        # Convert counts to percentages of total samples
        sector_bins: list[list[float]] = [[0.0] * 6 for _ in range(16)]
        sector_totals: list[float] = [0.0] * 16

        for s in range(16):
            for b in range(6):
                pct = (sector_counts[s][b] / total_samples) * 100.0 if total_samples > 0 else 0.0
                sector_bins[s][b] = pct
                sector_totals[s] += pct

        # Find prevailing sector
        prevailing_sec = 0
        max_sec_val = -1.0
        for s in range(16):
            if sector_totals[s] > max_sec_val:
                max_sec_val = sector_totals[s]
                prevailing_sec = s

        speed_dist_pct = [
            (cnt / total_samples) * 100.0 if total_samples > 0 else 0.0
            for cnt in speed_dist_counts
        ]

        units_cfg = self.config_manager.get("units", {}) if self.config_manager else {}
        w_unit = str(units_cfg.get("wind", "m/s"))

        self.canvas.set_data(
            sector_bins=sector_bins,
            sector_totals=sector_totals,
            calm_pct=calm_pct,
            speed_dist=speed_dist_pct,
            gust_speed=max_period_gust,
            curr_speed=curr_speed,
            curr_dir=curr_dir,
            prevailing_sector=prevailing_sec,
            prevailing_pct=max_sec_val,
            lang=self._lang,
            wind_unit=w_unit,
        )
