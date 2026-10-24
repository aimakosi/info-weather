"""PySide6 Desktop Weather Widget Window (KDE Plasma Optimized).

Provides:
- Frameless translucent desktop widget with KWin blur support.
- Mouse dragging anywhere on the widget.
- Mouse wheel for smooth debounced city cycling.
- Context menu and QSystemTrayIcon for desktop integration.
- Modular Gis-Weather blocks with live 2D (X/Y) coordinate offsets.
- Automatic solar theme switching and weather alerts.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from core.astronomy import determine_solar_time_of_day
from core.i18n import set_language, t
from core.logging import get_logger
from core.notifications import NotificationEngine
from models.weather import WeatherForecastData
from ui.blocks import (
    AdditionalInfoBlockWidget,
    AstronomyBlockWidget,
    DailyBlockWidget,
    DayPeriodsBlockWidget,
    HeaderBlockWidget,
    WindBlockWidget,
)
from ui.dialogs import CitySearchDialogQt, DetailedForecastDialogQt, SettingsDialogQt
from ui.effects.weather_effects import WeatherEffectsCanvas, resolve_effect_from_wmo
from ui.qt_compat import (
    QApplication,
    QBitmap,
    QColor,
    QFont,
    QFrame,
    QHBoxLayout,
    QIcon,
    QLinearGradient,
    QMenu,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPoint,
    QRectF,
    QRegion,
    QSizePolicy,
    QSystemTrayIcon,
    Qt,
    QtCore,
    QTimer,
    QVBoxLayout,
    QWheelEvent,
    QWidget,
    Signal,
)
from ui.utils import (
    get_weather_icon_path,
    is_system_light_theme,
    set_current_icon_theme,
    set_on_all_desktops,
    set_skip_taskbar,
)

logger = get_logger("ui.widget_window")


class WeatherContainerWidget(QWidget):
    """Custom container widget supporting landmark image backgrounds, gradient opacity, and rounded clipping."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WeatherWidgetContainer")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._landmark_pixmap: QPixmap | None = None
        self._seasonal_pixmap: QPixmap | None = None
        self._is_light: bool = False
        self._opacity: float = 1.0

        # Child effects canvas
        self.effects_layer = WeatherEffectsCanvas(self)
        self.effects_layer.lower()
        self._effects_mask_size: tuple[int, int] | None = None

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self.effects_layer.setGeometry(self.rect())
        self._update_effects_mask()

    def _update_effects_mask(self) -> None:
        """Clip the effects overlay to the seasonal card artwork.

        The seasonal theme is a transparent PNG whose card "floats" over the
        desktop.  Full-rectangle effects (sun rays, clouds, fog, lightning)
        must not paint over the transparent margins around the card, otherwise
        they expose a visible rectangle instead of the floating silhouette.
        """
        layer = self.effects_layer
        if (
            self._seasonal_pixmap is None
            or self._seasonal_pixmap.isNull()
            or layer.width() <= 0
            or layer.height() <= 0
        ):
            layer.clearMask()
            self._effects_mask_size = None
            return

        size = (layer.width(), layer.height())
        if size == self._effects_mask_size:
            return

        scaled = self._seasonal_pixmap.scaled(
            layer.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        alpha_mask = scaled.toImage().createAlphaMask()
        layer.setMask(QRegion(QBitmap.fromImage(alpha_mask)))
        self._effects_mask_size = size

    def set_seasonal_background(
        self,
        image_path: str,
        opacity: float = 1.0,
    ) -> None:
        p = Path(image_path)
        if p.is_file():
            self._seasonal_pixmap = QPixmap(str(p))
        else:
            self._seasonal_pixmap = None
        self._landmark_pixmap = None
        self._is_light = True
        self._opacity = opacity
        self._effects_mask_size = None
        self._update_effects_mask()
        self.update()

    def clear_seasonal_background(self) -> None:
        self._seasonal_pixmap = None
        self._effects_mask_size = None
        self.effects_layer.clearMask()
        self.update()

    def set_landmark_background(
        self,
        image_path: str,
        dimming: float = 0.35,
        blur_radius: float = 3.0,
        is_light: bool = True,
        opacity: float = 1.0,
    ) -> None:
        from core.landmark import process_landmark_image

        w = max(100, self.width())
        h = max(60, self.height())
        cached_path = process_landmark_image(
            source_path=image_path,
            target_w=w,
            target_h=h,
            dimming=dimming,
            blur_radius=blur_radius,
            is_light=is_light,
        )
        if cached_path and cached_path.is_file():
            self._landmark_pixmap = QPixmap(str(cached_path))
        else:
            self._landmark_pixmap = None

        self._is_light = is_light
        self._opacity = opacity
        self.update()

    def clear_landmark_background(self, is_light: bool = True, opacity: float = 1.0) -> None:
        self._landmark_pixmap = None
        self._is_light = is_light
        self._opacity = opacity
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect_f = QRectF(self.rect())
        op = max(0.2, min(1.0, self._opacity))

        # Seasonal theme: floating card with protruding 3D decorations and natural soft shadow
        if self._seasonal_pixmap and not self._seasonal_pixmap.isNull():
            painter.setOpacity(op)
            painter.drawPixmap(rect_f, self._seasonal_pixmap, QRectF(self._seasonal_pixmap.rect()))
            painter.setOpacity(1.0)
            return

        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect_f, 18.0, 18.0)
        painter.setClipPath(clip_path)

        # Gradient translucent background
        # In night mode: top is more transparent, bottom is more opaque
        grad = QLinearGradient(0.0, 0.0, 0.0, float(self.height()))
        if self._is_light:
            # Daytime light blue translucent gradient
            a_top = int(round(0.60 * op * 255))
            a_mid = int(round(0.84 * op * 255))
            a_bot = int(round(0.96 * op * 255))
            grad.setColorAt(0.0, QColor(196, 228, 252, a_top))
            grad.setColorAt(0.45, QColor(157, 211, 248, a_mid))
            grad.setColorAt(1.0, QColor(121, 190, 244, a_bot))
        else:
            # Nighttime: top has higher transparency (more transparent), bottom has less transparency (more opaque)
            a_top = int(round(0.52 * op * 255))
            a_mid = int(round(0.78 * op * 255))
            a_bot = int(round(0.96 * op * 255))
            grad.setColorAt(0.0, QColor(16, 19, 24, a_top))
            grad.setColorAt(0.45, QColor(10, 12, 16, a_mid))
            grad.setColorAt(1.0, QColor(5, 6, 8, a_bot))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(rect_f, 18.0, 18.0)

        # Border
        painter.setClipping(False)
        if self._is_light:
            border_pen = QPen(QColor(2, 132, 199, 76), 1.0)
        else:
            border_pen = QPen(QColor(148, 163, 184, 51), 1.0)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect_f.adjusted(0.5, 0.5, -0.5, -0.5), 18.0, 18.0)
        painter.end()


class WeatherWidgetWindowQt(QWidget):
    """Main frameless translucent desktop weather widget."""

    data_updated_signal = Signal(object)

    def __init__(self, provider: Any, config_manager: Any, parent: QWidget | None = None, app: Any = None):
        super().__init__(parent)
        self._hidden_owner: QWidget | None = None
        self.provider = provider
        self.config_manager = config_manager
        set_language(self.config_manager.get("app_language", "ru"))
        self.notification_engine = NotificationEngine()

        self._last_data: WeatherForecastData | None = None
        self._drag_pos = QPoint()
        self._press_pos: QPoint | None = None
        self._lock_position = False
        self._wheel_last_ts = 0.0

        self.city_dialog: CitySearchDialogQt | None = None
        self.settings_dialog: SettingsDialogQt | None = None
        self.detailed_dialog: DetailedForecastDialogQt | None = None

        self.blocks: list[QWidget] = []

        # Window Flags & Transparency
        wb_cfg = self.config_manager.get("window_behavior", {}) or {}
        show_taskbar = bool(wb_cfg.get("show_in_taskbar", False))
        always_on_top = bool(wb_cfg.get("always_on_top", False))
        init_type = Qt.WindowType.Window if show_taskbar else Qt.WindowType.Tool
        flags = Qt.WindowType.FramelessWindowHint | init_type
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags |= Qt.WindowType.WindowStaysOnBottomHint
        self.setWindowFlags(flags)
        # NOTE: Do NOT set WA_X11NetWmWindowTypeDock — KDE Plasma treats DOCK
        # windows as panels (strut reservation, edge snapping, special stacking).
        # Qt.WindowType.Tool already maps to _NET_WM_WINDOW_TYPE_UTILITY which
        # is properly excluded from the KDE task manager without side effects.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("info-weather")
        self.setObjectName("info-weather")

        # Main Root Layout
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(10, 10, 10, 8)

        # Translucent Container with landmark and effects support
        self.container = WeatherContainerWidget(self)
        self.effects_layer = self.container.effects_layer
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(14, 10, 14, 8)
        self.container_layout.setSpacing(2)
        self.outer_layout.addWidget(self.container)

        # Build initial blocks
        self._build_blocks()
        self._apply_theme()
        self._apply_window_behavior()
        self._connect_system_theme()

        app_instance = QApplication.instance()
        if app_instance is not None and hasattr(app_instance, "aboutToQuit"):
            app_instance.aboutToQuit.connect(self._save_window_position)

        # Connect signals
        self.data_updated_signal.connect(self._on_weather_updated_main_thread)
        if hasattr(self.provider, "add_data_listener"):
            self.provider.add_data_listener(self._on_provider_data)
        else:
            self.provider.on_data_updated = self._on_provider_data

        # Setup System Tray Icon
        self._setup_tray_icon()

        # Immediately display cached data (instant startup without blank screen or freeze)
        self._load_cached_forecast_initially()

        # Setup Periodic Update Timer
        self.update_timer = QTimer(self)
        interval_min = int(self.config_manager.get("update_interval_minutes", 60))
        self.update_timer.timeout.connect(lambda: self.refresh_forecast(force=False))
        self.update_timer.start(interval_min * 60 * 1000)

        # Trigger background network refresh after event loop starts (non-blocking)
        QTimer.singleShot(100, lambda: self.refresh_forecast(force=False))

    def _load_cached_forecast_initially(self) -> None:
        """Immediately display cached or offline baseline weather to prevent blank screen / freeze."""
        try:
            info = self.provider.get_active_city_info()
            if hasattr(self.provider, "get_cached_forecast"):
                cached = self.provider.get_cached_forecast(
                    lat=info["lat"],
                    lon=info["lon"],
                    city_name=info.get("name", ""),
                    country=info.get("country", ""),
                )
                if isinstance(cached, WeatherForecastData):
                    self._on_weather_updated_main_thread(cached)
        except Exception as e:
            logger.warning("Failed to load initial cached forecast: %s", e)

    def present(self) -> None:
        self.show()
        wb_cfg = self.config_manager.get("window_behavior", {}) or {}
        if wb_cfg.get("always_on_top", False):
            self.raise_()
            self.activateWindow()
        else:
            self.lower()

    # -------------------------------------------------------------------------
    # Block Assembly & 2D Offsets
    # -------------------------------------------------------------------------
    def _wrap_offset(
        self,
        widget: QWidget,
        ox: int,
        oy: int,
        scale: float,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
    ) -> QWidget:
        """Wrap a block widget into an offset container."""
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(alignment)

        sx = int(ox * scale)
        sy = int(oy * scale)
        widget.setContentsMargins(
            max(0, sx),
            max(0, sy),
            max(0, -sx),
            max(0, -sy),
        )
        layout.addWidget(widget)
        return wrapper

    def _build_blocks(self) -> None:
        """Build modular Gis-Weather blocks with 2D offsets."""
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.blocks.clear()

        skin_cfg = self.config_manager.get("skin", {})
        scale = float(skin_cfg.get("scale", 1.0))
        view_cfg = self.config_manager.get("view_blocks", {})
        formats_cfg = self.config_manager.get("formats", {}) or {}
        small_font_family = str(skin_cfg.get("small_font_family", "") or "")
        try:
            small_font_size = int(skin_cfg.get("small_font_size", 9))
        except (TypeError, ValueError):
            small_font_size = 9
        weekend_days = str(formats_cfg.get("weekend", "Sa, Su") or "Sa, Su")
        weekend_color = str(skin_cfg.get("weekend_color", "#ef4444") or "#ef4444")
        date_format = str(formats_cfg.get("date_format", "DD.MM") or "DD.MM")

        # Top Deck (Wind, Today, Header/Now, Additional Info, Tomorrow)
        weather_lang = self.config_manager.get("weather_language", "ru")
        units_cfg = self.config_manager.get("units", {}) or {}
        t_unit = "fahrenheit" if str(units_cfg.get("temp", "C")).lower() == "f" else "celsius"
        w_unit = str(units_cfg.get("wind", "m/s"))
        top_deck = QWidget()
        deck_layout = QHBoxLayout(top_deck)
        deck_layout.setContentsMargins(0, 0, 0, 0)
        deck_layout.setSpacing(max(6, int(16 * scale)))
        deck_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        has_deck = False

        # 1. Wind Block
        wind_cfg = dict(view_cfg.get("wind", {}))
        wind_cfg["lang"] = weather_lang
        wind_cfg["wind_unit"] = w_unit
        wind_cfg["arrow_color"] = str(skin_cfg.get("wind_arrow_color", "#f97316") or "#f97316")
        if wind_cfg.get("enabled", True):
            blk_wind = WindBlockWidget(options=wind_cfg, scale=scale)
            blk_wind.clicked.connect(lambda: self.open_detailed_dialog(screen_index=2))
            self.blocks.append(blk_wind)
            deck_layout.addWidget(self._wrap_offset(blk_wind, wind_cfg.get("offset_x", 0), wind_cfg.get("offset_y", 0), scale))
            has_deck = True

        # 2. Today Periods Block
        today_cfg = dict(view_cfg.get("today", {}))
        today_cfg["lang"] = weather_lang
        today_cfg["temp_unit"] = t_unit
        today_title = "Сьогодні" if weather_lang == "uk" else ("Today" if weather_lang == "en" else "Сегодня")
        today_cfg["mode"] = "today"
        today_cfg["title"] = today_title
        if today_cfg.get("enabled", False):
            blk_today = DayPeriodsBlockWidget(options=today_cfg, scale=scale)
            self.blocks.append(blk_today)
            deck_layout.addWidget(self._wrap_offset(blk_today, today_cfg.get("offset_x", 0), today_cfg.get("offset_y", 0), scale))
            has_deck = True

        # 3. Header / Now Block
        now_cfg = dict(view_cfg.get("now", {}))
        now_cfg["lang"] = weather_lang
        now_cfg["temp_unit"] = t_unit
        now_cfg["wind_unit"] = w_unit
        now_cfg["date_format"] = date_format
        if now_cfg.get("enabled", True):
            blk_now = HeaderBlockWidget(options=now_cfg, scale=scale)
            self.blocks.append(blk_now)
            deck_layout.addWidget(self._wrap_offset(blk_now, now_cfg.get("offset_x", 0), now_cfg.get("offset_y", 0), scale))
            has_deck = True

        # 4. Additional Info Block
        add_cfg = dict(view_cfg.get("additional_info", {}))
        add_cfg["lang"] = weather_lang
        add_cfg["temp_unit"] = t_unit
        add_cfg["wind_unit"] = w_unit
        add_cfg["pressure_unit"] = str(units_cfg.get("pressure", "mmHg"))
        if add_cfg.get("enabled", False):
            blk_add = AdditionalInfoBlockWidget(options=add_cfg, scale=scale)
            self.blocks.append(blk_add)
            deck_layout.addWidget(self._wrap_offset(blk_add, add_cfg.get("offset_x", 0), add_cfg.get("offset_y", 0), scale))
            has_deck = True

        # 5. Tomorrow Periods Block
        tom_cfg = dict(view_cfg.get("tomorrow", {}))
        tom_cfg["lang"] = weather_lang
        tom_cfg["temp_unit"] = t_unit
        tom_cfg["small_font_family"] = small_font_family
        tom_cfg["small_font_size"] = small_font_size
        tom_title = "Завтра" if weather_lang in ("ru", "uk") else "Tomorrow"
        tom_cfg["mode"] = "tomorrow"
        tom_cfg["title"] = tom_title
        if tom_cfg.get("enabled", True):
            blk_tom = DayPeriodsBlockWidget(options=tom_cfg, scale=scale)
            self.blocks.append(blk_tom)
            deck_layout.addWidget(self._wrap_offset(blk_tom, tom_cfg.get("offset_x", 0), tom_cfg.get("offset_y", 0), scale))
            has_deck = True

        if has_deck:
            self.container_layout.addWidget(top_deck)

        # 6. Astronomy Strip (compact, left-aligned)
        astro_cfg = dict(view_cfg.get("astronomy", {}))
        astro_cfg["lang"] = weather_lang
        daily_cfg = view_cfg.get("daily", {})
        astro_enabled = bool(astro_cfg.get("enabled", True))
        daily_enabled = bool(daily_cfg.get("enabled", True))

        if astro_enabled:
            # Ultra-compact astronomy strip placed cleanly beneath top deck
            astro_section = QWidget()
            astro_section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            astro_section_l = QVBoxLayout(astro_section)
            astro_section_l.setContentsMargins(0, 0, 0, 0)
            astro_section_l.setSpacing(1)

            blk_astro = AstronomyBlockWidget(options=astro_cfg, scale=scale)
            self.blocks.append(blk_astro)
            astro_section_l.addWidget(
                self._wrap_offset(
                    blk_astro,
                    astro_cfg.get("offset_x", 0),
                    astro_cfg.get("offset_y", 0),
                    scale,
                    alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                )
            )

            if daily_enabled:
                sep2 = QFrame()
                sep2.setObjectName("BlockSeparator")
                sep2.setFrameShape(QFrame.Shape.HLine)
                sep2.setFixedHeight(1)
                astro_section_l.addWidget(sep2)

            self.container_layout.addWidget(astro_section)

        # 7. Daily Forecast Strip (Horizontal layout matching Gis-Weather)
        if daily_enabled:
            if not astro_enabled:
                sep2 = QFrame()
                sep2.setObjectName("BlockSeparator")
                sep2.setFrameShape(QFrame.Shape.HLine)
                self.container_layout.addWidget(sep2)

            d_opts = dict(daily_cfg)
            d_opts["horizontal"] = True
            d_opts["lang"] = weather_lang
            d_opts["temp_unit"] = t_unit
            d_opts["small_font_family"] = small_font_family
            d_opts["small_font_size"] = small_font_size
            d_opts["weekend"] = weekend_days
            d_opts["weekend_color"] = weekend_color
            d_opts["date_format"] = date_format
            blk_daily = DailyBlockWidget(options=d_opts, scale=scale)
            self.blocks.append(blk_daily)
            self.container_layout.addWidget(self._wrap_offset(blk_daily, daily_cfg.get("offset_x", 0), daily_cfg.get("offset_y", 0), scale))

        # Enforce minimum width so horizontal multi-day forecast strip and deck fit cleanly
        min_w = max(470, int(490 * scale))
        self.container.setMinimumWidth(min_w)
        self.setMinimumWidth(min_w + 20)
        self.adjustSize()

    # -------------------------------------------------------------------------
    # Theme & Styling
    # -------------------------------------------------------------------------
    def _connect_system_theme(self) -> None:
        """Repaint when KDE / Qt Application Style color scheme changes."""
        try:
            app = QApplication.instance()
            hints = app.styleHints() if app else None
            if hints is not None and hasattr(hints, "colorSchemeChanged"):
                hints.colorSchemeChanged.connect(self._on_system_theme_changed)
            if app is not None and hasattr(app, "paletteChanged"):
                app.paletteChanged.connect(self._on_system_theme_changed)
        except Exception as e:
            logger.debug("System color scheme signal unavailable: %s", e)

    def _on_system_theme_changed(self, *_args: Any) -> None:
        skin_cfg = self.config_manager.get("skin", {})
        if skin_cfg.get("theme_mode") == "auto_system":
            self._apply_theme()
            if self._last_data:
                for blk in self.blocks:
                    blk.update(self._last_data)
            self._adapt_window_size()

    def _adapt_window_size(self) -> None:
        """Shrink or expand window to tightly fit contents and layout constraints."""
        self.container.adjustSize()
        self.adjustSize()
        self.resize(0, 0)
        QTimer.singleShot(0, self._shrink_to_fit)

    def _shrink_to_fit(self) -> None:
        """Post-event-loop adjustment once pending layout recalculations finish."""
        try:
            if not self.isMaximized() and not self.isFullScreen():
                self.container.adjustSize()
                self.adjustSize()
                self.resize(0, 0)
        except RuntimeError:
            pass

    def _apply_theme(self) -> None:
        skin_cfg = self.config_manager.get("skin", {})
        icon_theme = skin_cfg.get("icons_name", "svg")
        set_current_icon_theme(icon_theme)

        theme_mode = skin_cfg.get("theme_mode", "auto_solar")
        opacity = float(skin_cfg.get("opacity", 0.90))

        # Main font follows the Appearance setting; forecast labels are tagged
        # with the "smallFont" property and get the small font via QSS below.
        font_family = str(skin_cfg.get("font_family", "") or "").strip()
        font_css = ""
        if font_family:
            family = font_family.replace("\\", "\\\\").replace('"', '\\"')
            font_css = (
                "\nQWidget#WeatherWidgetContainer, "
                f'QWidget#WeatherWidgetContainer QWidget {{ font-family: "{family}"; }}'
            )
            small_family = str(skin_cfg.get("small_font_family", "") or "").strip()
            if small_family:
                small_family = small_family.replace("\\", "\\\\").replace('"', '\\"')
                font_css += (
                    "\nQWidget#WeatherWidgetContainer QWidget[smallFont=\"true\"] "
                    f'{{ font-family: "{small_family}"; }}'
                )
            try:
                font_size = int(skin_cfg.get("font_size", 10))
            except (TypeError, ValueError):
                font_size = 10
            self.container.setFont(QFont(font_family, font_size))

        is_light = False
        if theme_mode == "day":
            is_light = True
        elif theme_mode == "night":
            is_light = False
        elif theme_mode == "auto_system":
            is_light = is_system_light_theme()
        elif theme_mode == "auto_solar" and self._last_data:
            lat = self._last_data.lat or 55.75
            lon = self._last_data.lon or 37.61
            s_time = determine_solar_time_of_day(
                lat, lon,
                utc_offset_hours=self._last_data.utc_offset_seconds / 3600.0,
            )
            is_light = (s_time[0] == "day")

        op = max(0.2, min(1.0, opacity))

        # Check seasonal theme configuration (primary daytime theme)
        seasonal_cfg = self.config_manager.get("seasonal_theme", {})
        seasonal_enabled = bool(seasonal_cfg.get("enabled", True))
        seasonal_mode = str(seasonal_cfg.get("mode", "auto"))

        resolved_seasonal = None
        if is_light and seasonal_enabled and theme_mode != "auto_system":
            from core.seasonal import resolve_seasonal_theme_image
            resolved_seasonal = resolve_seasonal_theme_image(seasonal_mode)

        scale = float(skin_cfg.get("scale", 1.0))
        if resolved_seasonal and resolved_seasonal.is_file():
            theme_class = "light-theme"
            self.container.set_seasonal_background(str(resolved_seasonal), opacity=op)
            self.container.setStyleSheet("""
                QWidget#WeatherWidgetContainer {
                    background: transparent;
                    border: none;
                }
            """ + font_css)
            # Safe inner margins so content stays cleanly inside the card body
            self.container_layout.setContentsMargins(48, 48, 46, 34)
            min_w = max(550, int(570 * scale))
            min_h = max(315, int(330 * scale))
            self.container.setMinimumSize(min_w, min_h)
            self.setMinimumSize(min_w + 20, min_h + 18)
        else:
            self.container.clear_seasonal_background()
            self.container.clear_landmark_background(is_light=is_light, opacity=op)
            self.container_layout.setContentsMargins(14, 10, 14, 8)
            min_w = max(470, int(490 * scale))
            self.container.setMinimumSize(min_w, 0)
            self.setMinimumSize(min_w + 20, 0)
            if is_light:
                theme_class = "light-theme"
                # Light blue rather than washed-out white
                a_top = round(0.60 * op, 2)
                a_mid = round(0.84 * op, 2)
                a_bot = round(0.96 * op, 2)
                self.container.setStyleSheet(f"""
                    QWidget#WeatherWidgetContainer {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 rgba(196, 228, 252, {a_top}),
                            stop:0.45 rgba(157, 211, 248, {a_mid}),
                            stop:1 rgba(121, 190, 244, {a_bot}));
                        border-radius: 18px;
                        border: 1px solid rgba(2, 132, 199, 0.30);
                    }}
                """ + font_css)
            else:
                theme_class = ""
                # Near-black gradient with a subtle cool tint
                a_top = round(0.52 * op, 2)
                a_mid = round(0.78 * op, 2)
                a_bot = round(0.96 * op, 2)
                self.container.setStyleSheet(f"""
                    QWidget#WeatherWidgetContainer {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 rgba(16, 19, 24, {a_top}),
                            stop:0.45 rgba(10, 12, 16, {a_mid}),
                            stop:1 rgba(5, 6, 8, {a_bot}));
                        border-radius: 18px;
                        border: 1px solid rgba(148, 163, 184, 0.20);
                    }}
                """ + font_css)

        # Toggle the theme class so QSS label colors switch accordingly
        if self.container.property("class") != theme_class:
            self.container.setProperty("class", theme_class)
            for widget in [self.container] + self.container.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)

        # Update dynamic weather effects
        if hasattr(self, "effects_layer"):
            landmark_cfg = self.config_manager.get("landmark", {})
            forced_eff = landmark_cfg.get("active_effect", "auto")
            effects_enabled = landmark_cfg.get("weather_effects", True) and (forced_eff != "none")
            if effects_enabled and hasattr(self, "_last_data") and self._last_data:
                cur = self._last_data.current
                wmo_code = cur.weather_code
                w_spd = cur.wind_speed or 3.0
                w_deg = cur.wind_direction or 135.0
                is_day = bool(cur.is_day)

                eff = forced_eff if forced_eff and forced_eff != "auto" else resolve_effect_from_wmo(wmo_code, wind_speed=w_spd, is_day=is_day)

                anim_mode = self.config_manager.get("animation_mode", "balanced")
                self.effects_layer.set_effect(
                    effect_name=eff,
                    wind_deg=w_deg,
                    wind_spd=w_spd,
                    is_light=is_light,
                    animation_mode=anim_mode,
                )
            else:
                self.effects_layer.set_effect("none")

        if self.city_dialog:
            self.city_dialog._apply_theme()
            self.city_dialog._refresh_cities_list()
        if self.detailed_dialog:
            self.detailed_dialog._apply_dialog_theme()

        self._adapt_window_size()

    # -------------------------------------------------------------------------
    # Window Behavior (Lock, Always on top, All desktops)
    # -------------------------------------------------------------------------
    def _apply_window_behavior(self) -> None:
        cfg = self.config_manager.get("window_behavior", {}) or {}
        was_locked = self._lock_position
        self._lock_position = bool(cfg.get("lock_position", False))
        always_on_top = bool(cfg.get("always_on_top", False))
        on_all_desktops = bool(cfg.get("on_all_desktops", False))
        show_in_taskbar = bool(cfg.get("show_in_taskbar", False))

        flags = self.windowFlags()
        # Window type occupies the lowest byte (Window, Dialog, Tool, ...).
        # Drop it as a whole: overlapping bitmasks make "flags & ~Tool" wrong.
        desired = flags & ~0xFF
        if not show_in_taskbar:
            # Tool/utility windows are omitted from the KDE/Windows taskbar and
            # window list, which is the expected behavior for a desktop widget.
            desired |= Qt.WindowType.Tool
        else:
            desired |= Qt.WindowType.Window

        desired &= ~Qt.WindowType.WindowStaysOnTopHint
        desired &= ~Qt.WindowType.WindowStaysOnBottomHint
        if always_on_top:
            desired |= Qt.WindowType.WindowStaysOnTopHint
        else:
            desired |= Qt.WindowType.WindowStaysOnBottomHint

        # WA_X11NetWmWindowTypeDock removed: see note in __init__.

        if desired != flags:
            was_visible = self.isVisible()
            pos = self.pos()
            self.setWindowFlags(desired)
            self.move(pos)
            # setWindowFlags() recreates the native window; apply the EWMH
            # state while it is still unmapped so the taskbar never sees it.
            self._apply_ewmh_window_state(show_in_taskbar, on_all_desktops)
            if was_visible:
                self.show()
                if always_on_top:
                    self.raise_()
                else:
                    self.lower()
        else:
            self._apply_ewmh_window_state(show_in_taskbar, on_all_desktops)

        # Remember the current position when the user locks the widget.
        if self._lock_position and not was_locked and self.isVisible():
            self._save_window_position()

        # EWMH "on all desktops" can be dropped while the window is mapped.
        if on_all_desktops:
            QTimer.singleShot(300, self._reapply_on_all_desktops)

    def _apply_ewmh_window_state(self, show_in_taskbar: bool, on_all_desktops: bool) -> None:
        """Apply taskbar / desktop EWMH properties to the native window."""
        try:
            window_id = int(self.winId())
        except Exception:
            return
        if not window_id:
            return
        applied = set_on_all_desktops(window_id, on_all_desktops)
        if on_all_desktops and not applied:
            logger.info(
                "On-all-desktops is only supported on X11; keeping the window on the current desktop"
            )
        set_skip_taskbar(window_id, not show_in_taskbar)

    def _save_window_position(self) -> None:
        """Persist the current top-left position for the next launch."""
        cfg = dict(self.config_manager.get("window_position", {}) or {})
        if not cfg.get("save_position", True) or not self.isVisible():
            return
        pos = self.pos()
        if (
            cfg.get("saved")
            and cfg.get("x") == pos.x()
            and cfg.get("y") == pos.y()
        ):
            return
        cfg["x"] = int(pos.x())
        cfg["y"] = int(pos.y())
        cfg["saved"] = True
        self.config_manager.set("window_position", cfg)

    def restore_saved_position(self) -> bool:
        """Move the window to the saved position if it is still on-screen."""
        cfg = self.config_manager.get("window_position", {}) or {}
        if not cfg.get("save_position", True) or not cfg.get("saved", False):
            return False

        x, y = cfg.get("x"), cfg.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return False

        app = QApplication.instance()
        if app is None:
            return False

        target = QtCore.QRect(int(x), int(y), self.width(), self.height())
        for screen in app.screens():
            geo = screen.availableGeometry()
            if not geo.intersects(target):
                continue
            max_x = max(geo.left(), geo.right() - self.width() + 1)
            max_y = max(geo.top(), geo.bottom() - self.height() + 1)
            self.move(
                min(max(int(x), geo.left()), max_x),
                min(max(int(y), geo.top()), max_y),
            )
            return True
        return False

    def _reapply_on_all_desktops(self) -> None:
        cfg = self.config_manager.get("window_behavior", {}) or {}
        if not bool(cfg.get("on_all_desktops", False)):
            return
        try:
            window_id = int(self.winId())
        except Exception:
            return
        if window_id:
            set_on_all_desktops(window_id, True)

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        cfg = self.config_manager.get("window_behavior", {}) or {}
        show_in_taskbar = bool(cfg.get("show_in_taskbar", False))
        try:
            window_id = int(self.winId())
        except Exception:
            window_id = 0
        if window_id:
            # Safety net for the case where the window was already mapped
            # (e.g. re-show after hide); no KWin reloads needed.
            set_skip_taskbar(window_id, not show_in_taskbar)
            if not show_in_taskbar:
                # Some WMs only accept the EWMH state once the window is
                # actually mapped; one cheap retry, no KWin reconfigure.
                QTimer.singleShot(100, lambda: set_skip_taskbar(window_id, True))

    # -------------------------------------------------------------------------
    # Mouse Interaction (Drag & Wheel City Switcher)
    # -------------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            if not self._lock_position:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._lock_position:
            return
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_dragging = not self._drag_pos.isNull()
        drag_dist = 0
        if self._press_pos is not None:
            drag_dist = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
        self._drag_pos = QPoint()
        self._press_pos = None
        if was_dragging:
            self._save_window_position()
        if event.button() == Qt.MouseButton.LeftButton and drag_dist <= 5:
            self.open_detailed_dialog()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: Any) -> None:
        self._save_window_position()
        if hasattr(self, "update_timer") and self.update_timer.isActive():
            self.update_timer.stop()
        if getattr(self, "_hidden_owner", None):
            try:
                self._hidden_owner.close()
            except Exception:
                pass
        super().closeEvent(event)
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.config_manager.get("wheel_city_switch", True):
            return

        now = time.time()
        debounce_sec = float(self.config_manager.get("wheel_debounce_ms", 400)) / 1000.0
        if now - self._wheel_last_ts < debounce_sec:
            return

        self._wheel_last_ts = now
        cities = list(self.config_manager.get("cities", []))
        if len(cities) <= 1:
            return

        curr_name = self.config_manager.get("current_city", "")
        curr_idx = 0
        for idx, c in enumerate(cities):
            if c.get("name") == curr_name:
                curr_idx = idx
                break

        direction = 1 if event.angleDelta().y() < 0 else -1
        next_idx = (curr_idx + direction) % len(cities)
        next_city = cities[next_idx]

        self.config_manager.set("current_city", next_city.get("name", ""))
        self._apply_theme()
        self.refresh_forecast(city_info=next_city, force=False)
        event.accept()

    # -------------------------------------------------------------------------
    # Context Menu
    # -------------------------------------------------------------------------
    def contextMenuEvent(self, event: Any) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.15); padding: 4px; border-radius: 6px; } QMenu::item:selected { background-color: #38bdf8; color: #0f172a; }")

        act_detailed = menu.addAction(t("menu_detailed"))
        act_detailed.triggered.connect(self.open_detailed_dialog)
        f_det = act_detailed.font()
        f_det.setBold(True)
        act_detailed.setFont(f_det)

        act_refresh = menu.addAction(t("menu_refresh"))
        act_refresh.triggered.connect(lambda: self.refresh_forecast(force=True))

        menu.addSeparator()

        act_cities = menu.addAction(t("menu_cities"))
        act_cities.triggered.connect(self.open_city_dialog)

        # Theme modes submenu
        menu_theme = menu.addMenu(t("menu_theme"))
        act_auto = menu_theme.addAction(t("theme_solar"))
        act_auto.triggered.connect(lambda: self._set_theme_mode("auto_solar"))
        act_day = menu_theme.addAction(t("theme_day"))
        act_day.triggered.connect(lambda: self._set_theme_mode("day"))
        act_night = menu_theme.addAction(t("theme_night"))
        act_night.triggered.connect(lambda: self._set_theme_mode("night"))

        menu.addSeparator()

        act_settings = menu.addAction(t("menu_settings"))
        act_settings.triggered.connect(self.open_settings_dialog)

        menu.addSeparator()

        act_quit = menu.addAction(t("menu_close"))
        act_quit.triggered.connect(QApplication.instance().quit)

        menu.exec(event.globalPos())

    def _set_theme_mode(self, mode: str) -> None:
        skin = dict(self.config_manager.get("skin", {}))
        skin["theme_mode"] = mode
        self.config_manager.set("skin", skin)
        self._apply_theme()
        if self._last_data:
            for blk in self.blocks:
                blk.update(self._last_data)
        self._adapt_window_size()

    # -------------------------------------------------------------------------
    # Dialogs
    # -------------------------------------------------------------------------
    def open_detailed_dialog(self, screen_index: int = 0) -> None:
        if not self.detailed_dialog:
            self.detailed_dialog = DetailedForecastDialogQt(
                parent=None,
                config_manager=self.config_manager,
                data=self._last_data,
            )
        elif self._last_data:
            self.detailed_dialog.update_data(self._last_data)
        self.detailed_dialog.set_screen(screen_index)
        self.detailed_dialog.show()
        self.detailed_dialog.raise_()
        self.detailed_dialog.activateWindow()

    def open_city_dialog(self) -> None:
        if not self.city_dialog:
            self.city_dialog = CitySearchDialogQt(
                parent=self,
                config_manager=self.config_manager,
                weather_provider=self.provider,
                on_city_changed=self._on_city_selected,
            )
        else:
            self.city_dialog.retranslate_ui()
            self.city_dialog._apply_theme()
            self.city_dialog._refresh_cities_list()
        self.city_dialog.present()

    def open_settings_dialog(self) -> None:
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialogQt(
                parent=self,
                config_manager=self.config_manager,
                on_config_changed=self._on_config_changed,
            )
        else:
            self.settings_dialog.retranslate_ui()
        self.settings_dialog.position_relative_to_widget(self)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _on_city_selected(self, city_dict: dict[str, Any]) -> None:
        self.config_manager.set("current_city", city_dict.get("name", ""))
        self._apply_theme()
        self.refresh_forecast(city_info=city_dict, force=True)

    def _on_config_changed(self) -> None:
        if hasattr(self.provider, "apply_network_config"):
            try:
                self.provider.apply_network_config()
            except Exception as e:
                logger.warning("Failed to apply network settings: %s", e)
        app_lang = self.config_manager.get("app_language", "ru")
        if app_lang == "auto" or app_lang not in ("ru", "uk", "en"):
            app_lang = "ru"
        set_language(app_lang)
        weather_lang = self.config_manager.get("weather_language", "ru")
        if weather_lang == "auto" or weather_lang not in ("ru", "uk", "en"):
            weather_lang = app_lang
        prev_lang = getattr(self.provider, "lang", None) if hasattr(self, "provider") and self.provider else None
        if hasattr(self, "provider") and self.provider:
            self.provider.lang = weather_lang
        if self.city_dialog:
            self.city_dialog.retranslate_ui()
        self._build_blocks()
        self._apply_theme()
        self._apply_window_behavior()
        # Restart the update timer so an interval change takes effect immediately
        if hasattr(self, "update_timer"):
            interval_min = int(self.config_manager.get("update_interval_minutes", 60))
            self.update_timer.setInterval(max(1, interval_min) * 60 * 1000)
        if hasattr(self, "tray") and self.tray:
            self._setup_tray_icon()
        display_mode = self.config_manager.get("display_mode", "both")
        if display_mode == "indicator_only":
            self.hide()
            if hasattr(self, "tray") and self.tray:
                self.tray.show()
        elif display_mode == "widget_only":
            self.show()
            if hasattr(self, "tray") and self.tray:
                self.tray.hide()
        else:  # both
            self.show()
            if hasattr(self, "tray") and self.tray:
                self.tray.show()
        if self._last_data:
            from data.resources import localize_city
            loc_name, _ = localize_city(
                name=self._last_data.city_name,
                lat=self._last_data.lat,
                lon=self._last_data.lon,
                country=self._last_data.country,
                lang=weather_lang,
            )
            self._last_data.city_name = loc_name
            for blk in self.blocks:
                blk.update(self._last_data)
            if hasattr(self, "tray") and self.tray:
                cur = self._last_data.current
                from data.wmo_conditions import get_condition_text
                cond_str = get_condition_text(cur.weather_code, lang=weather_lang, is_day=bool(cur.is_day)) if cur.weather_code is not None else (cur.condition_text or "")
                tip = f"{self._last_data.city_name}: {cur.temp:+0.0f}°C, {cond_str}" if cond_str else f"{self._last_data.city_name}: {cur.temp:+0.0f}°C"
                self.tray.setToolTip(tip)
        if self.detailed_dialog:
            self.detailed_dialog.retranslate_ui()
        if prev_lang and prev_lang != weather_lang:
            self.refresh_forecast(force=True)
        self._adapt_window_size()

    # -------------------------------------------------------------------------
    # System Tray Icon
    # -------------------------------------------------------------------------
    def _setup_tray_icon(self) -> None:
        is_new = not hasattr(self, "tray") or self.tray is None
        if is_new:
            self.tray = QSystemTrayIcon(self)
            self.tray.activated.connect(self._on_tray_activated)

        icon_path = get_weather_icon_path("weather-few-clouds.svg")
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))

        tray_menu = QMenu()
        tray_menu.setStyleSheet("QMenu { background-color: #1e293b; color: #f8fafc; border: 1px solid rgba(255,255,255,0.15); padding: 4px; border-radius: 6px; } QMenu::item:selected { background-color: #38bdf8; color: #0f172a; }")

        act_show = tray_menu.addAction(t("tray_toggle"))
        act_show.triggered.connect(self._toggle_visibility)

        act_detailed = tray_menu.addAction(t("menu_detailed"))
        act_detailed.triggered.connect(self.open_detailed_dialog)

        act_refresh = tray_menu.addAction(t("menu_refresh"))
        act_refresh.triggered.connect(lambda: self.refresh_forecast(force=True))

        act_settings = tray_menu.addAction(t("menu_settings"))
        act_settings.triggered.connect(self.open_settings_dialog)

        tray_menu.addSeparator()

        act_quit = tray_menu.addAction(t("tray_quit"))
        act_quit.triggered.connect(QApplication.instance().quit)

        self.tray.setContextMenu(tray_menu)
        display_mode = self.config_manager.get("display_mode", "both")
        if display_mode == "widget_only":
            self.tray.hide()
        else:
            self.tray.show()

    def _toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._toggle_visibility()

    # -------------------------------------------------------------------------
    # Forecast Refresh & Threaded Handling
    # -------------------------------------------------------------------------
    def refresh_forecast(self, city_info: dict[str, Any] | None = None, force: bool = False) -> None:
        info = city_info or self.provider.get_active_city_info()
        # If switching cities, immediately display that city's cached weather if available
        if city_info and hasattr(self.provider, "get_cached_forecast"):
            try:
                cached = self.provider.get_cached_forecast(
                    lat=info["lat"],
                    lon=info["lon"],
                    city_name=info.get("name", ""),
                    country=info.get("country", ""),
                )
                if isinstance(cached, WeatherForecastData):
                    self._on_weather_updated_main_thread(cached)
            except Exception as e:
                logger.debug("City switch cached forecast lookup: %s", e)

        self.provider.fetch_forecast_async(
            lat=info["lat"],
            lon=info["lon"],
            city_name=info["name"],
            country=info.get("country", ""),
            force_refresh=force,
            tz_name=info.get("timezone", ""),
        )

    def _on_provider_data(self, data: WeatherForecastData) -> None:
        self.data_updated_signal.emit(data)

    def _on_weather_updated_main_thread(self, data: WeatherForecastData) -> None:
        self._last_data = data
        self._apply_theme()

        for blk in self.blocks:
            blk.update(data)

        self._adapt_window_size()

        if self.detailed_dialog and self.detailed_dialog.isVisible():
            self.detailed_dialog.update_data(data)

        # Update Tray Icon & Tooltip
        cur = data.current
        weather_lang = self.config_manager.get("weather_language", "ru")
        from data.wmo_conditions import get_condition_text
        cond_str = get_condition_text(cur.weather_code, lang=weather_lang, is_day=bool(cur.is_day)) if cur.weather_code is not None else (cur.condition_text or "")
        tip = f"{data.city_name}: {cur.temp:+0.0f}°C, {cond_str}" if cond_str else f"{data.city_name}: {cur.temp:+0.0f}°C"
        self.tray.setToolTip(tip)

        icon_path = get_weather_icon_path(cur.icon_name or cur.weather_code, is_day=cur.is_day, code=cur.weather_code)
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))

        # Check and send desktop notifications (only for fresh online data, not offline/cached)
        if not getattr(data, "is_offline", False):
            self._check_notifications(data)

    def _check_notifications(self, data: WeatherForecastData) -> None:
        notif_cfg = self.config_manager.get("notifications", {})
        if not notif_cfg.get("enabled", True):
            return

        lang = self.config_manager.get("app_language", "ru")
        events = self.notification_engine.check_notifications(
            current_fc=data,
            config=self.config_manager.all(),
            lang=lang,
        )

        for ev in events:
            if self.tray.supportsMessages():
                self.tray.showMessage(
                    ev.title,
                    ev.body,
                    QSystemTrayIcon.MessageIcon.Information,
                    5000,
                )


WidgetWindow = WeatherWidgetWindowQt
