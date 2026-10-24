"""PySide6 Wind Compass block with Variant 1 nautical compass rose («Морской штурвал»)."""

from __future__ import annotations

import math
from typing import Any

from core.i18n import get_current_language, t
from core.units import (
    format_wind_speed,
    get_beaufort_name,
    get_beaufort_number,
)
from data.wmo_conditions import (
    COMPASS_CARDINALS_4,
    COMPASS_INTERCARDINALS_4,
)
from models.weather import WeatherForecastData
from ui.qt_compat import (
    QColor,
    QFont,
    QLabel,
    QMouseEvent,
    QPainter,
    QPen,
    QPoint,
    QPointF,
    QPolygonF,
    QRectF,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from ui.utils import is_light_theme_widget

BIN_COLORS = [
    QColor("#3b82f6"),  # < 2 m/s
    QColor("#06b6d4"),  # 2 - 4 m/s
    QColor("#10b981"),  # 4 - 6 m/s
    QColor("#eab308"),  # 6 - 8 m/s
    QColor("#f97316"),  # 8 - 11 m/s
    QColor("#ef4444"),  # > 11 m/s
]


class WindCompassCanvas(QWidget):
    """Custom canvas drawing nautical compass rose with rotating cross and antique dial."""

    def __init__(
        self,
        size: int | None = None,
        width: int | None = None,
        height: int | None = None,
        arrow_color: str = "#f97316",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        if width is not None and height is not None:
            self.canvas_w = width
            self.canvas_h = height
        elif size is not None:
            self.canvas_w = int(size * 1.38)
            self.canvas_h = size
        else:
            self.canvas_w = 136
            self.canvas_h = 98

        self.canvas_size = self.canvas_h  # Backward compatibility
        self.arrow_color = QColor(arrow_color)
        if not self.arrow_color.isValid():
            self.arrow_color = QColor("#f97316")
        self.setFixedSize(self.canvas_w, self.canvas_h)
        self.angle: float = 0.0  # Meteorological wind direction (where wind comes from)
        self.wind_speed: float = 0.0
        self.lang: str = "ru"

        # 16-sector stacked distribution data (kept for backward compatibility)
        self._sector_bins: list[list[float]] = [[0.0] * 6 for _ in range(16)]
        self._sector_totals: list[float] = [0.0] * 16
        self._calm_pct: float = 0.0
        self._max_pct: float = 25.0

    def set_wind(self, degrees: float, angle_offset: float = 0.0, lang: str = "ru") -> None:
        self.angle = (degrees + angle_offset) % 360.0
        self.lang = lang
        self.update()

    def set_distribution(
        self,
        sector_bins: list[list[float]],
        sector_totals: list[float],
        calm_pct: float,
    ) -> None:
        self._sector_bins = sector_bins
        self._sector_totals = sector_totals
        self._calm_pct = calm_pct
        max_sec = max(sector_totals) if sector_totals else 0.0
        self._max_pct = max(15.0, max_sec)
        self.update()

    def _is_light_theme(self) -> bool:
        """Detect the container's light-theme class for painted colors."""
        return is_light_theme_widget(self)

    @staticmethod
    def _polar(cx: float, cy: float, rx: float, ry: float, degrees: float) -> QPointF:
        rad = math.radians(degrees)
        return QPointF(
            cx + rx * math.sin(rad),
            cy - ry * math.cos(rad),
        )

    @staticmethod
    def _polar_r(cx: float, cy: float, r: float, degrees: float) -> QPointF:
        rad = math.radians(degrees)
        return QPointF(
            cx + r * math.sin(rad),
            cy - r * math.cos(rad),
        )

    @staticmethod
    def _draw_faceted_ray(
        painter: QPainter,
        cx: float,
        cy: float,
        length: float,
        half_width: float,
        deg: float,
        col_light: QColor,
        col_dark: QColor,
        pen_border: QPen,
        hatch: bool = False,
        is_light_theme: bool = False,
    ) -> None:
        tip = WindCompassCanvas._polar_r(cx, cy, length, deg)
        p_left = WindCompassCanvas._polar_r(cx, cy, half_width, deg - 90.0)
        p_right = WindCompassCanvas._polar_r(cx, cy, half_width, deg + 90.0)
        center = QPointF(cx, cy)

        # Left facet (light)
        poly_left = QPolygonF([center, p_left, tip])
        painter.setPen(pen_border)
        painter.setBrush(col_light)
        painter.drawPolygon(poly_left)

        # Right facet (dark / shaded)
        poly_right = QPolygonF([center, tip, p_right])
        painter.setBrush(col_dark)
        painter.drawPolygon(poly_right)

        if hatch:
            p_step = 6
            hatch_pen = QPen(
                QColor(15, 23, 42, 38) if is_light_theme else QColor(255, 255, 255, 38),
                0.7,
            )
            painter.setPen(hatch_pen)
            for i in range(1, p_step):
                t_val = i / float(p_step)
                p1 = QPointF(
                    center.x() + (tip.x() - center.x()) * t_val,
                    center.y() + (tip.y() - center.y()) * t_val,
                )
                p2 = QPointF(
                    p_right.x() + (tip.x() - p_right.x()) * (t_val * 0.8),
                    p_right.y() + (tip.y() - p_right.y()) * (t_val * 0.8),
                )
                painter.drawLine(p1, p2)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        light = self._is_light_theme()
        w = float(self.canvas_w)
        h = float(self.canvas_h)
        cx, cy = w / 2.0, h / 2.0
        r_max = min(w, h) * 0.35
        r_inner = r_max * 0.72

        c_ring = QColor(15, 23, 42, 70) if light else QColor(255, 255, 255, 55)
        c_tick = QColor(15, 23, 42, 90) if light else QColor(255, 255, 255, 75)
        c_text_main = QColor("#0284c7") if light else QColor("#38bdf8")
        c_text_card = QColor("#0f172a") if light else QColor("#f8fafc")
        c_text_sub = QColor("#64748b") if light else QColor("#94a3b8")

        # 1. Scalloped / Serrated rim (inspired by antique compass in Wind-Rose.jpg)
        r_teeth_out = r_max * 1.05
        r_teeth_in = r_max
        num_teeth = 16
        tooth_pts: list[QPointF] = []
        for i in range(num_teeth):
            deg_mid = i * (360.0 / num_teeth)
            deg_step = (360.0 / num_teeth) / 2.0
            tooth_pts.append(self._polar_r(cx, cy, r_teeth_out, deg_mid))
            tooth_pts.append(self._polar_r(cx, cy, r_teeth_in, deg_mid + deg_step))
        painter.setPen(QPen(c_ring, 0.8))
        painter.setBrush(QColor(0, 0, 0, 6) if light else QColor(255, 255, 255, 6))
        painter.drawPolygon(QPolygonF(tooth_pts))

        # 2. Concentric dual border rings
        painter.setPen(QPen(c_ring, 1.3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r_max, r_max)
        painter.drawEllipse(QPointF(cx, cy), r_inner, r_inner)

        r_hairline = (r_max + r_inner) / 2.0
        painter.setPen(QPen(c_ring, 0.6, Qt.PenStyle.DashLine))
        painter.drawEllipse(QPointF(cx, cy), r_hairline, r_hairline)

        # 3. Radial graduated hatch ticks (32 divisions)
        num_ticks = 32
        for i in range(num_ticks):
            deg = i * (360.0 / num_ticks)
            is_cardinal = (i % 8 == 0)
            is_sub = (i % 4 == 0)
            r_start = r_inner
            r_end = r_max if is_cardinal else (r_max * 0.96 if is_sub else r_hairline)
            painter.setPen(QPen(c_tick if (is_cardinal or is_sub) else c_ring, 1.2 if is_cardinal else 0.8))
            painter.drawLine(self._polar_r(cx, cy, r_start, deg), self._polar_r(cx, cy, r_end, deg))

        # 4. Outward guide ticks
        for deg in (0.0, 90.0, 180.0, 270.0):
            painter.setPen(QPen(c_text_main if deg == 0.0 else c_tick, 1.2))
            painter.drawLine(self._polar_r(cx, cy, r_teeth_out, deg), self._polar_r(cx, cy, r_max * 1.14, deg))

        # 5. Cardinal Letters (С, В, Ю, З / N, E, S, W / Пн, Сх, Пд, Зх)
        card_labels = COMPASS_CARDINALS_4.get(self.lang, COMPASS_CARDINALS_4["ru"])
        f_main = QFont("Georgia", max(8, int(r_max * 0.22)), QFont.Weight.Bold)
        f_main.setStyleHint(QFont.StyleHint.Serif)
        painter.setFont(f_main)
        r_lbl = r_max * 1.25
        for lbl, deg in zip(card_labels, (0.0, 90.0, 180.0, 270.0)):
            pt = self._polar_r(cx, cy, r_lbl, deg)
            painter.setPen(c_text_main if deg == 0.0 else c_text_card)
            box_w = max(18.0, r_max * 0.52)
            painter.drawText(
                QRectF(pt.x() - box_w / 2.0, pt.y() - box_w / 2.0, box_w, box_w),
                Qt.AlignmentFlag.AlignCenter,
                lbl,
            )

        # 6. Intercardinal Letters (СЗ, СВ, ЮВ, ЮЗ / NW, NE, SE, SW / ПнЗ, ПнС, ПдС, ПдЗ)
        sub_labels = COMPASS_INTERCARDINALS_4.get(self.lang, COMPASS_INTERCARDINALS_4["ru"])
        f_sub = QFont("Georgia", max(6, int(r_max * 0.14)), QFont.Weight.Bold)
        f_sub.setStyleHint(QFont.StyleHint.Serif)
        painter.setFont(f_sub)
        r_sub = r_max * 1.21
        for lbl, deg in zip(sub_labels, (315.0, 45.0, 135.0, 225.0)):
            pt = self._polar_r(cx, cy, r_sub, deg)
            painter.setPen(c_text_sub)
            box_w = max(18.0, r_max * 0.48)
            painter.drawText(
                QRectF(pt.x() - box_w / 2.0, pt.y() - box_w / 2.0, box_w, box_w),
                Qt.AlignmentFlag.AlignCenter,
                lbl,
            )

        # 7. Subtle fixed 8-pointed compass star underlay
        pen_subtle = QPen(QColor(15, 23, 42, 28) if light else QColor(255, 255, 255, 26), 0.7)
        c_star_l = QColor(15, 23, 42, 12) if light else QColor(255, 255, 255, 12)
        c_star_d = QColor(15, 23, 42, 22) if light else QColor(255, 255, 255, 5)
        for i in range(8):
            deg = i * 45.0
            self._draw_faceted_ray(
                painter,
                cx,
                cy,
                r_max * 0.85,
                r_max * 0.12,
                deg,
                c_star_l,
                c_star_d,
                pen_subtle,
                hatch=False,
                is_light_theme=light,
            )

        # 8. Rotating 4-point Nautical Cross
        # Wind direction: pointer points to the direction the wind comes from (e.g. SE -> points to SE)
        wind_angle = self.angle % 360.0

        pen_ray = QPen(QColor(15, 23, 42, 90) if light else QColor(0, 0, 0, 85), 0.9)
        c_silver_l = QColor(241, 245, 249, 230) if light else QColor(226, 232, 240, 210)
        c_silver_d = QColor(71, 85, 105, 220) if light else QColor(100, 116, 139, 200)

        cross_len = r_max * 0.82
        cross_w = r_max * 0.16

        # Lateral arms (orthogonal to wind direction)
        for offset in (90.0, -90.0):
            self._draw_faceted_ray(
                painter,
                cx,
                cy,
                cross_len * 0.75,
                cross_w * 0.85,
                wind_angle + offset,
                c_silver_l,
                c_silver_d,
                pen_ray,
                hatch=True,
                is_light_theme=light,
            )

        # Tail arm (opposite to wind direction)
        self._draw_faceted_ray(
            painter,
            cx,
            cy,
            cross_len * 0.65,
            cross_w,
            wind_angle + 180.0,
            c_silver_l,
            c_silver_d,
            pen_ray,
            hatch=True,
            is_light_theme=light,
        )

        # Active forward pointer (flame amber / accent, points to current wind direction)
        if self.arrow_color.isValid() and self.arrow_color.name().lower() not in ("#f97316", "#ef4444"):
            col_act_l = self.arrow_color
            col_act_d = self.arrow_color.darker(135)
            pen_active = QPen(self.arrow_color.darker(150) if light else self.arrow_color.lighter(135), 1.1)
            core_color = self.arrow_color
        else:
            col_act_l = QColor("#f97316")  # Flame amber
            col_act_d = QColor("#c2410c")  # Shaded crimson
            pen_active = QPen(QColor("#7c2d12") if light else QColor("#ffedd5"), 1.2)
            core_color = QColor("#f97316")

        self._draw_faceted_ray(
            painter,
            cx,
            cy,
            r_max * 1.15,
            cross_w * 1.12,
            wind_angle,
            col_act_l,
            col_act_d,
            pen_active,
            hatch=False,
            is_light_theme=light,
        )

        # 9. Central antique metal hub (NO numbers!)
        r_pin = r_max * 0.15
        painter.setPen(QPen(QColor("#0f172a") if light else QColor("#ffffff"), 1.3))
        painter.setBrush(QColor("#ffffff") if light else QColor("#1e293b"))
        painter.drawEllipse(QPointF(cx, cy), r_pin, r_pin)

        # Central accent rivet core
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(core_color)
        painter.drawEllipse(QPointF(cx, cy), r_pin * 0.48, r_pin * 0.48)


class WindBlockWidget(QWidget):
    """Wind block showing nautical compass rose («Морской штурвал»)."""

    clicked = Signal()

    def __init__(self, options: dict[str, Any] | None = None, scale: float = 1.0, parent: QWidget | None = None):
        super().__init__(parent)
        self.options = options or {}
        self.scale = scale
        self.angle_offset = float(self.options.get("angle", 0))
        self.widget = self

        self.wind_speed: float = 0.0
        self.wind_dir: float = 0.0
        self.wind_cardinal: str = "N"
        self._press_pos: QPoint | None = None

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Nautical compass canvas dimensions scaled: ~136 × 98 px
        c_w = max(110, int(136 * scale))
        c_h = max(78, int(98 * scale))
        self.compass = WindCompassCanvas(
            width=c_w,
            height=c_h,
            arrow_color=str(self.options.get("arrow_color", "#f97316")),
        )
        layout.addWidget(self.compass, alignment=Qt.AlignmentFlag.AlignCenter)

        # Kept as invisible attribute for backward compatibility with tests
        self.lbl_text = QLabel("—")
        self.lbl_text.setObjectName("WindText")
        self.lbl_text.setVisible(False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            cur_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            drag_dist = (cur_pos - self._press_pos).manhattanLength() if self._press_pos is not None else 0
            self._press_pos = None
            if drag_dist <= 6:
                self.clicked.emit()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def update(self, data: WeatherForecastData) -> None:
        cur = data.current
        self.wind_speed = cur.wind_speed
        self.wind_dir = float(cur.wind_direction)

        weather_lang = self.options.get("lang")
        wind_unit = self.options.get("wind_unit", "m_s")

        if weather_lang:
            from data.wmo_conditions import get_wind_direction_info
            card_abbr, card_full = get_wind_direction_info(self.wind_dir, lang=weather_lang)
            self.wind_cardinal = card_abbr if card_abbr != "--" else (cur.wind_cardinal or "—")
            spd_str = format_wind_speed(self.wind_speed, wind_unit, lang=weather_lang)
            desc = card_full if card_full != "--" else self.wind_cardinal
            tip_lang = weather_lang
        else:
            self.wind_cardinal = cur.wind_cardinal or "—"
            spd_str = format_wind_speed(self.wind_speed, wind_unit)
            desc = self.wind_cardinal
            tip_lang = get_current_language()

        # 24h wind distribution for 16-ray minimal wind rose
        sector_counts: list[list[int]] = [[0] * 6 for _ in range(16)]
        calm_count = 0
        total_samples = 0

        hourly_samples = data.hourly[:24] if data.hourly else []
        if not hourly_samples and data.days_detailed:
            d0 = data.days_detailed[0]
            for h in range(min(24, len(d0.hourly_winds))):
                spd = d0.hourly_winds[h]
                d_val = d0.hourly_wind_dirs[h] if len(d0.hourly_wind_dirs) > h else self.wind_dir
                total_samples += 1
                if spd < 0.5:
                    calm_count += 1
                else:
                    b_idx = 0 if spd < 2 else (1 if spd < 4 else (2 if spd < 6 else (3 if spd < 8 else (4 if spd < 11 else 5))))
                    sec = int(((d_val % 360.0) + 11.25) / 22.5) % 16
                    sector_counts[sec][b_idx] += 1
        else:
            for h in hourly_samples:
                total_samples += 1
                spd = h.wind_speed
                d_val = h.wind_direction
                if spd < 0.5:
                    calm_count += 1
                else:
                    b_idx = 0 if spd < 2 else (1 if spd < 4 else (2 if spd < 6 else (3 if spd < 8 else (4 if spd < 11 else 5))))
                    sec = int(((d_val % 360.0) + 11.25) / 22.5) % 16
                    sector_counts[sec][b_idx] += 1

        if total_samples > 0:
            sector_bins: list[list[float]] = [[0.0] * 6 for _ in range(16)]
            sector_totals: list[float] = [0.0] * 16
            for s in range(16):
                for b in range(6):
                    pct = (sector_counts[s][b] / total_samples) * 100.0
                    sector_bins[s][b] = pct
                    sector_totals[s] += pct
            calm_pct = (calm_count / total_samples) * 100.0
            self.compass.set_distribution(sector_bins, sector_totals, calm_pct)

        self.compass.set_wind(self.wind_dir, self.angle_offset, lang=weather_lang or get_current_language())
        self.compass.wind_speed = self.wind_speed
        self.lbl_text.setText(f"{self.wind_cardinal}, {spd_str}")

        b_num = get_beaufort_number(self.wind_speed)
        b_name = get_beaufort_name(self.wind_speed, lang=tip_lang)
        deg_str = f"{int(round(self.wind_dir)) % 360}°"
        tip = f"{t('weather_wind', _lang=tip_lang)}: {desc} ({deg_str}), {spd_str} ({b_num} {t('unit_beaufort', _lang=tip_lang)} • {b_name})\n{t('switch_screen_hint', _lang=tip_lang)}"
        self.compass.setToolTip(tip)
        self.lbl_text.setToolTip(tip)
        self.setToolTip(tip)


WindBlock = WindBlockWidget
